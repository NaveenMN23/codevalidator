# Design Discussion: Lazily-Triggered Per-Problem Container Pooling

**Status:** Draft — design discussion, no implementation started.
**Companion to:** `repo-execution-architecture.md`, `execution-tradeoffs-and-timeout.md` (§3 Pooled Provisioning, §4 Deferred Eager)
**Scope:** Refines the pooled-provisioning model with a concrete trigger point (first request per problem) and concrete sizing numbers, and compares it against lazy / eager / deferred-eager with the cost and latency factors already established.

---

## 1. Origin of This Idea

The proposal that prompted this doc: since all users working on the same problem share the same pre-baked image/dependencies, why create a container per session at all? Instead, create a container **per problem**, keep it warm, and let different users' concurrent Run/Submit calls share it — paying the cold-start cost only for the first user, with everyone after getting a fast path.

The underlying instinct (reuse shared dependencies to avoid repeated cold starts) is correct and valuable. The literal mechanism as first proposed — multiple users' code executing inside **one shared running container** — has a critical flaw that needed correcting before sizing anything.

---

## 2. The Critical Correction: One Container Cannot Safely Serve Concurrent Different Users

A container is a single isolation boundary: one shared filesystem, one shared process/network namespace, one shared cgroup. If two different users' code ran inside the *same* container at the same time:

- **Filesystem collision** — both users' submitted files land in the same container filesystem. Without per-user chroot sandboxing inside the container (which would mean re-implementing isolation by hand — defeating the purpose of using containers at all), user A could read or overwrite user B's files.
- **Noisy-neighbor resource contention** — one user's infinite loop or memory-heavy code starves the other's execution, since both share the same cgroup limit. Not a "slows down a bit" problem — one user's bug breaks another user's grading.
- **Shared crash blast radius** — if user A's code crashes or OOMs the container, user B's concurrently-running execution dies too, collateral damage from someone else's bug. This directly violates the isolation/disposability/crash-containment properties already established as non-negotiable in `repo-execution-architecture.md` §6.
- **Worse for Java specifically** — if this meant literally one JVM process handling both users' code, that's shared classloader space and shared static state between two untrusted codebases. No real isolation remains at that point.

**Conclusion: never share one running container instance across concurrent different users' executions, regardless of how much it would save.** This is a security boundary, not a performance tuning knob.

---

## 3. The Corrected Model: Lazily-Triggered Per-Problem Pool

The underlying goal — "first user eats the cold start, everyone after gets it fast" — is achievable safely with one change: a **pool of multiple separate, pre-warmed container instances per problem**, where each execution claims its own instance. No instance is ever shared by two concurrent executions.

### 3.1 Flow

1. **First request for problem P** (cold, no warm instance exists) — pays full cold-start latency, and **also triggers the autoscaler** to spin up a few standby instances of P's image in the background, anticipating further demand. This is the "lazy trigger" — the pool isn't pre-warmed ahead of time (avoiding eager's waste on problems nobody's touching); it's triggered into existence by the first real request.
2. **Second user submits to problem P** shortly after, possibly while user A's execution is still running — they claim a **different, already-warm standby instance** from the now-forming pool, not user A's instance. Fast path.
3. **Further concurrent users** keep drawing from the pool the same way — each gets their own isolated container, just one that skipped the boot/pull cost because it was pre-warmed.
4. **Pool replenishes** in the background as instances are consumed and released (destroyed/reset after each use — see §6 on why destroy-and-replace is the safer default for untrusted code). If concurrent demand outpaces replenishment, overflow requests cold-start, same as the "pool temporarily exhausted" case already documented for pure pooled provisioning.

The one-word distinction that makes this safe: **"others get it fast" must mean "claiming a different pre-warmed instance," never "joining the first user's already-running container."**

### 3.2 Relationship to the existing models

This is `execution-tradeoffs-and-timeout.md` §3 (Pooled Provisioning) combined with §4's lazy-trigger principle (Deferred Eager) — §3 as originally written left the pre-warm trigger point open; this refinement pins it down explicitly: **pool creation is lazily triggered by the first real request for that problem**, not pre-warmed speculatively ahead of any demand.

---

## 4. Sizing the Pool With Numbers

Pool size should track **actual concurrent in-flight executions for that specific problem**, not total open sessions or total platform concurrency. The right tool for this is **Little's Law**: `concurrent in-flight = arrival rate × average service time`.

### 4.1 Per-execution duration (once warm-pool-claimed: sync + exec only, no boot)

| Framework | Average instance hold time per claim |
|---|---|
| Node.js | ~3-7s |
| Python/FastAPI | ~3-7s |
| Spring Boot/Java | ~5-10s |

### 4.2 Worked example — Java, ~10s average hold time, 20 students working the same problem

| Scenario | Submissions | Window | Arrival rate | Concurrent in-flight | Pool size needed |
|---|---|---|---|---|---|
| Normal day, moderately popular problem | 20 | 30 min | 0.011/s | 0.011 × 10 = **0.11** | 1-2 instances |
| Assignment due, most submit in the last 5 min | 20 | 5 min | 0.067/s | 0.067 × 10 = **0.67** | 2-3 instances |
| Hard deadline crunch, everyone submits in last 2 min | 20 | 2 min | 0.167/s | 0.167 × 10 = **1.67** | 4-5 instances (buffer for variance) |
| Live contest, literal simultaneous click | 20 | 10 sec | 2.0/s | 2.0 × 10 = **20** | 20+ instances — the one case that genuinely needs a large pool |

**Key finding:** because each execution is short-lived (~10s), even a problem with real popularity rarely has more than a handful of executions truly in flight at the same instant. Little's Law keeps instantaneous concurrency low unless arrivals are pathologically synchronized (a live contest countdown, not a normal homework deadline). A pool of **3-5 standby instances per popular problem** comfortably absorbs realistic deadline-crunch behavior; only a true "everyone clicks at second zero" scenario needs a much larger pool.

### 4.3 Cost

Using Java's reference cost (~$0.0449/container-hour, per `execution-tradeoffs-and-timeout.md` §2.3):

- A popular problem holding 5 standby instances for a 2-hour active window (e.g. the evening an assignment is due): `5 × $0.0449 × 2 ≈ $0.45` for that problem's entire active window.
- Even with **20 simultaneously "hot" problems** at once (generous — most platforms have a handful of genuinely active problems at a time, not dozens), each running a 3-5 instance pool for a couple hours: roughly `20 × $0.45 ≈ $9` for that whole burst window.
- Compare to flat eager's baseline of **~$1,460/month** (holding 67 containers per framework regardless of per-problem concurrency, per the earlier cost doc) — correctly-sized per-problem pooling is dramatically cheaper, because it scales with actual simultaneous in-flight executions per problem, not with how many sessions merely have a problem open.

### 4.4 Reconciling with node capacity

20 hot problems × 3-5 Java instances each ≈ 60-100 instances total ≈ **8-12 nodes** at the earlier m5.2xlarge sizing (~8 Java containers/node). A small, reasonable footprint — nowhere near requiring a large fleet.

### 4.5 The one real risk: ramp-up lag

If a problem goes from cold to suddenly popular faster than expected, the autoscaler needs to notice (queue depth growing) and react — and growing the pool itself takes one cold-start cycle (Java: 2-15s) before new standby instances are ready. There's a brief window, bounded by roughly one cold-start duration, where early arrivals during a sudden spike still queue or cold-start before the pool catches up. Small and self-limiting — not a sustained problem, just a short transient at the start of a sharp ramp. A deadline-aware pre-scaling signal (explicitly flagging "problem X is due at time T") can eliminate this for predictable spikes.

---

## 5. Comparison Against All Four Models

| | Lazy | Eager | Pure Pooled (per-challenge, pre-warmed ahead of demand) | Deferred Eager (session-scoped) | **Lazily-Triggered Per-Problem Pool (this doc)** |
|---|---|---|---|---|---|
| **Trigger point** | Every Run/Submit click | Problem open | Speculative, ahead of demand | First Run/Submit click in a session | First Run/Submit for that problem, platform-wide |
| **Sharing scope** | None — always fresh | None — single session | Shared pool, partitioned by challenge×framework | None — single session | Shared pool, partitioned by challenge×framework, lazily created |
| **Cost (200 concurrent users)** | Near-zero (~cents-$ total) | ~$1,460-4,390/month | Between lazy and eager, depends on pre-warm aggressiveness | ~Half of eager's tiered cost, or less | **Lowest of all models when correctly sized** — ~$9 for a generous 20-hot-problems burst scenario |
| **Latency on first request ever for a problem** | Full cold-start | N/A (pre-warmed at open) | Depends on pre-warm timing | Full cold-start | Full cold-start (same as lazy) |
| **Latency for concurrent/subsequent requests on the same problem** | Full cold-start every time | Near-instant if still warm | Near-instant if pool has a member | Near-instant only within the *same session* | **Near-instant for any user**, not just the same session — this is the unique advantage |
| **Idle-timeout/pool-sizing machinery** | None | Reaper + activity tracking, all open sessions | Autoscaler, pre-warmed ahead of demand | Reaper + activity tracking, engaged sessions only | Autoscaler reacting to per-problem queue depth, lazily triggered |
| **Cross-user reuse safety concern** | N/A | N/A | Real — needs destroy-and-replace discipline | N/A | **Real — needs destroy-and-replace discipline** |
| **Pre-warming lead time** | None | Known at problem-open | Speculative/predictive | None | None until first request; reactive after that |
| **Needs real telemetry to size correctly** | No | Some (idle-timeout tuning) | Yes (traffic concentration) | Some (idle-timeout tuning) | **Yes, the most of any model** (per-problem arrival rate, popularity distribution, synchronization patterns) |
| **Operational complexity** | Lowest | Moderate | High | Moderate | **Highest** |

### Why this model is unique

It's the only one where a fast path is available to a user who **never interacted with this problem before**, as long as someone else recently has — latency benefit is shared across the whole user population for a given problem, not scoped to one session's own prior activity (deferred eager's limitation) or requiring pre-emptive speculation (pure pooled's limitation without a lazy trigger).

---

## 6. Why This Isn't the Recommended Starting Point

Despite winning on cost and on latency-for-the-traffic-that-matters, this model is **not** where implementation should start:

1. **No telemetry exists yet to size it.** Pool sizing depends on real per-problem arrival patterns, popularity distribution, and arrival synchronization — none of which exist before Run/Submit is even built. Guessing these numbers risks the same failure mode as guessing the original flat 60-minute idle-timeout, except the failure mode here (queuing/cold-start exactly during a deadline crunch) is worse and more visible to users.
2. **It carries the platform's only real cross-user security tripwire.** Reusing a container instance across two different users' untrusted code requires a proven, reliable reset (or strict destroy-and-replace) discipline. A bug here doesn't just degrade UX — it risks leaking one user's code/state into another's execution. Not a place to cut corners before the simpler models have been validated end-to-end in production.
3. **It is strictly the most to build and operate**: per-problem pool management, an autoscaler reacting to queue depth, deadline-aware pre-scaling signals, and the reset/destroy safety discipline, plus monitoring for all of it — meaningful ongoing engineering surface with nothing yet built to attach it to.

This also mirrors why LeetCode/HackerRank's pooling only makes sense at their scale, with their simpler generic-per-language images (one pool serves the entire catalog for a language, no per-challenge partitioning). We'd be taking on the harder, per-challenge-image version of their pattern at a small fraction of their traffic — exactly the kind of complexity worth deferring until real data justifies it.

---

## 7. Recommendation / Staging

- **Phase 1 (build now): Deferred Eager**, per `execution-tradeoffs-and-timeout.md` §4. Simple, safe (no cross-user reuse risk), and already captures the latency win for the workflow that matters most — the edit-run-edit-run loop within one user's own session.
- **Phase 2 (telemetry-gated upgrade): Lazily-Triggered Per-Problem Pooling**, as detailed in this doc — but only for problems where real instrumented traffic (per-problem concurrency, time-to-first-click, popularity distribution, arrival synchronization) shows the complexity is worth it. Likely candidates first: high-traffic assigned coursework problems, and Java specifically, given it has by far the largest cold-start cost to amortize and therefore the most to gain from pooling.
- **Do not build Phase 2 speculatively.** The data this model needs to be sized correctly is a direct byproduct of running Phase 1 in production — there is no shortcut to it via estimation alone.
