# Design Discussion: Lazy vs. Eager Container Provisioning

**Status:** Draft — design discussion, no implementation started.
**Companion to:** `repo-execution-architecture.md` (§5 step 2, §8 item 2)
**Scope:** Compares lazy provisioning (container created only on Run/Submit click) against eager provisioning (container started when the problem opens) — advantages, disadvantages, cost, and latency for each, plus the open decision between them.

---

## 1. Lazy Provisioning (container created only on Run/Submit click)

Container lifecycle is scoped to a single action: create → sync files → exec → destroy. No container exists between actions. This is close to the pattern `platform-workers` already uses for grading today.

### 1.1 Advantages

1. **Zero cost for sessions that never click Run.** Browsing, reading, abandoning a problem costs nothing — no idle-hold spend at all.
2. **No idle-timeout policy needed.** No reaper, no "last activity" tracking, no idle window to manage.
3. **Eliminates the "container missing when action fires" failure path.** There's no presumption of an existing warm container, so there's no fallback-detection logic needed — every action is symmetric.
4. **Simpler mental model, smaller blast radius.** Container lifetime is tightly scoped to one action — easier to reason about, test, and clean up.
5. **Lower sustained concurrent container count.** Only currently-executing actions hold a container, not every open session.

### 1.2 Disadvantages

1. **Every click pays full cold-start latency — including repeat clicks.** No latency is hidden behind reading time; the cold-start tax is paid on every single Run, not just the first.
2. **No reuse across repeated Run clicks in an edit-run-edit-run loop.** A developer iterating re-pays the full cold-start cost every time — the most serious cost, since this is the platform's core workflow.
3. **Burstier peak load.** Container starts cluster around Run/Submit clicks (which themselves cluster around things like assignment deadlines) rather than being staggered across problem-open events — worse tail latency exactly when load is highest.
4. **Registry-cache unpredictability.** No lead time to pre-warm the right image on the right node before it's needed, unlike eager's "known at problem-open" advantage.
5. **Forecloses future JVM-warm-pool optimization.** Nothing persistent exists to warm if every container is always freshly created.

### 1.3 Cost

Per-invocation compute cost is tiny — this model only pays for actual execution time, never idle time.

| Framework | Boot + exec time (rough) | Cost per single Run/Submit |
|---|---|---|
| Node.js | ~3-6s total | ~$0.00003 |
| Python/FastAPI | ~3-7s total | ~$0.00004 |
| Spring Boot/Java | ~10-18s total (boot-dominated) | ~$0.0002 |

At 200 concurrent users, even with generous usage (~5 Run clicks + 1-2 Submits per session): **total compute cost is on the order of a few cents to low dollars** — roughly 1-2 orders of magnitude cheaper than eager with idle-timeout, because there's no cost for the empty space between clicks.

### 1.4 Latency

| Framework | Cold-start tax paid on **every** click |
|---|---|
| Node.js | ~0-1s pull (warm node cache) + 100-500ms boot ≈ **under 1.5s typically** |
| Python/FastAPI | ~0-1s pull + 300ms-1s boot ≈ **under 2s typically** |
| Spring Boot/Java | ~0-1s pull + **2-8s boot, up to 10-15s** with heavier starters — paid in full on *every* Run, not just the first |

Node/Python's cold-start is small enough to plausibly eat every click. Java's is not — repeatedly paying 2-8+ seconds on every iteration of an edit-run loop is a materially worse developer experience.

---

## 2. Eager Provisioning (container starts when the problem opens)

Container starts as soon as the user opens the problem, before Run is clicked. The backend hands the browser a session handle; by the time Run is clicked, the container is hopefully already warm.

### 2.1 Advantages

1. **Hides boot latency behind reading time.** The entire reason eager exists — for Java specifically, this is the only model that makes the 2-8s (up to 15s) JVM tax invisible to the user.
2. **Run feels instant on the common path.** If the container is already warm, Run only pays file-sync + exec time, not boot time.
3. **Spreads load over time, not into bursts.** Container starts are triggered by staggered "problem opened" events rather than clustering around Run-click bursts.
4. **Predictable pre-warming.** Knowing which image a session needs at problem-open time gives lead time to ensure that image is cached on the assigned node before it's needed.
5. **Enables future optimizations lazy forecloses** — e.g. a JVM warm-pool has somewhere to live in this model.

### 2.2 Disadvantages

1. **Pays for containers that are never used.** Every "opened but never clicked Run" session still spins up and holds a container — pure waste, structurally unavoidable since you don't know in advance who'll click Run.
2. **Idle-timeout policy becomes mandatory machinery.** Requires a reaper, "last activity" tracking, and a tiered idle-timeout + hard-cap design — none of which lazy needs.
3. **Reintroduces the "container missing when action fires" problem.** If idle-timeout reclaims the container before Run is clicked, the action still falls back to a cold reprovision — paying idle-hold cost *and* full cold-start latency.
4. **Doubles orchestration load relative to action-scoped containers.** Steady-state concurrent container count tracks open sessions, not actions in flight — strictly higher than lazy's footprint at any moment.
5. **More moving parts overall** — session-state tracking, idle-timeout reaper, eager-trigger-on-open logic — additional surfaces to build, test, and operate.

### 2.3 Cost

Eager's cost floor is fundamentally higher than lazy's by construction — it pays to hold capacity ahead of demand, including demand that never materializes. Using the same reference pricing (~$0.0225/hr Node, ~$0.0236/hr Python, ~$0.0449/hr Java per container) at 200 concurrent users (67/framework):

| Idle-timeout policy | Cost at 8 active hrs/day |
|---|---|
| **No reclaim / flat 60-min hold** (worst case) | ~$49/day → **~$1,460/month** |
| **Sustained 24/7 at 200 concurrent** (ceiling, unrealistic) | ~$146/day → **~$4,390/month** |
| **Tiered 5-10 min idle-timeout** (recommended if eager is chosen) | Materially lower than the flat-60 figure, since stale containers get reclaimed quickly — exact number depends on real session abandon-rate data not yet available. Still strictly *above* lazy's cost. |
| **Lazy, for comparison** | A few cents to low single-digit dollars total |

The gap between eager (even well-tuned) and lazy is: `(opened-but-never-ran rate) × (idle-timeout window) × (container cost)`. That's a real, unavoidable premium eager pays for hiding boot latency.

### 2.4 Latency

| Framework | If container still warm at click time | If idle-timeout already reclaimed it (cold fallback) |
|---|---|---|
| Node.js | Near-instant — just file-sync + exec | Same as lazy's cold-start: ~1-1.5s |
| Python/FastAPI | Near-instant | Same as lazy's cold-start: ~1-2s |
| Spring Boot/Java | Near-instant — the entire point of eager | Full 2-8s (up to 15s) — identical to lazy's worst case, the exact scenario eager exists to prevent |

The latency win is entirely conditional on the container still being alive at click time. A too-aggressive idle-timeout (set for cost control) increases how often the cold fallback fires — giving eager's cost *and* lazy's latency, the worst of both. The benefit only holds if the idle-timeout is generous enough that most sessions Run before it fires, which pushes cost back up toward the higher end of the table above.

---

## 3. Pooled Provisioning (shared warm pool, partitioned by challenge × framework)

**Reference:** this is the pattern online judges like LeetCode and HackerRank actually use at scale — neither per-session eager, nor per-click cold lazy. Both explicitly call fresh-container-per-submission a non-starter once past toy traffic ("3-5s cold start" per request), and both converge on an async queue feeding a pool of already-running, pre-warmed containers that any incoming submission can claim. Isolation is enforced by a supervisor process outside the sandbox (cgroup limits, syscall interception, network lockdown, non-root user) — the same category of control `platform-workers`' `DOCKER_MEM_LIMIT`/`DOCKER_TIMEOUT_SECONDS` pattern already applies.

### 3.1 How it would work for us

- For each **challenge × framework** image, maintain a small pool of containers that are already past the expensive part (ECR pull done, process/JVM already booted), sized to that challenge's recent/expected concurrent Run rate.
- An incoming Run/Submit request claims a free instance from that challenge's pool, instead of holding a per-session container (eager) or cold-starting from zero (lazy).
- After use, the container is either wiped back to a clean baseline and returned to the pool, or destroyed and replaced — see §3.4 on why destroy-and-replace is the safer default here.
- A background autoscaler keeps each pool topped up: grows it ahead of predicted demand (traffic history, scheduled deadlines/contests), shrinks it when a challenge goes quiet.
- Requests flow through an async queue: if a pool is briefly exhausted, the request waits rather than failing outright, and the autoscaler reacts to growing queue depth by expanding that pool.

### 3.2 Why our version is harder than LeetCode/HackerRank's

Their pools are **generic per-language judge sandboxes** — a single Python pool serves *any* Python submission for *any* problem, because their execution model is small stdin/stdout-style judging with no challenge-specific dependency tree. One pool per language, maximal reuse.

Our images are **per-challenge × per-framework**, with real dependency trees baked in (per `repo-execution-architecture.md` §4, a deliberate choice to support production-like repos). That means:
- We need **N separate pools** (one per active challenge × framework combination), not one pool per language.
- A pool's utilization is bounded by concurrent demand for *that specific challenge*, not platform-wide demand for that language.
- Rarely-opened challenges end up with small or empty pools most of the time, falling back to effectively-lazy cold-start — the pooling benefit concentrates on popular challenges (assigned coursework, trending problems), not the full catalog.

### 3.3 Advantages

1. **Avoids eager's biggest waste.** No per-open-session container — only enough warm capacity to match actual concurrent Run throughput for a given challenge.
2. **Avoids lazy's latency cost on the hot path.** A claimed pool member for a popular challenge is already booted — no ECR pull, no JVM startup.
3. **Tracks real traffic shape.** The autoscaler grows pools for currently-popular challenges and lets idle ones shrink to nothing — cost follows actual demand more tightly than either single-mode model.
4. **No per-session idle-timeout/reaper logic at all.** Container "warm-ness" is fully decoupled from any individual user's session lifecycle — pool sizing is the only lever, not per-user activity tracking.
5. **Smooths predictable bursts.** If the autoscaler is given a heads-up (scheduled contest start, known assignment deadline), it can pre-grow the relevant pool ahead of the surge, absorbing it with already-warm capacity instead of a stampede of simultaneous cold starts.

### 3.4 Disadvantages

1. **The most complex of the three models to build and operate.** Requires per-challenge×framework pool management, an autoscaler reacting to queue depth/demand signals, and a reliable reset-between-reuses mechanism.
2. **Reset-between-reuses is a real security/correctness risk if done incorrectly.** Reusing a container across two different users' untrusted code requires guaranteeing zero leakage — filesystem, memory, env vars, leftover processes. The safer default is **destroy-and-replace** rather than wipe-and-reuse given the code is untrusted, which gives up some of the "skip the boot cost" benefit on every claim, not just some.
3. **Cold/unpopular challenges get no benefit.** For the long tail of rarely-opened problems, the pool is empty most of the time — effectively identical to pure lazy for that traffic, so the win is concentrated on a subset of challenges, not the whole catalog.
4. **Predictive autoscaling lags reality.** Sizing pools ahead of demand needs historical traffic data per challenge, or reactive scaling that's inherently a step behind sudden spikes — overflow requests during a spike still cold-start.
5. **New operational surface.** Pool-exhaustion policy (queue-and-wait vs. reject vs. fallback-to-cold-start), per-challenge pool hit/miss-rate monitoring, and per-pool sizing tuning are all new things to build, observe, and operate that neither pure lazy nor pure eager require.

### 3.5 Cost

Sits between lazy and eager, and is the hardest of the three to estimate without real traffic data — it depends on:

- **How concentrated demand is.** A few popular challenges driving most traffic (vs. a long uniform tail) makes pooling much more cost-efficient; a flat, uniform distribution across many challenges makes it look more like lazy with extra operational overhead and little payoff.
- **How aggressively pools are kept sized vs. demand.** A generously-sized pool behaves cost-wise close to eager (paying for capacity ahead of need); a tightly-sized pool behaves close to lazy with occasional warm hits.

**Rough framing:** for challenges with a high pool hit-rate, compute cost approaches eager's idle-hold cost for that subset; for cold/unpopular challenges, cost approaches lazy's near-zero. Given the typical "few popular, long unpopular tail" shape of coding-platform traffic, total cost is likely much closer to lazy's end of the range than eager's, while still cutting most of the cold-start latency for the traffic that actually matters. **This needs real per-challenge popularity/traffic-distribution data to model with any precision** — a third "needs telemetry" item, alongside the two already flagged in §6.

### 3.6 Latency

| Scenario | Latency |
|---|---|
| Popular challenge, pool has a free warm member | Near-instant — same as eager's best case |
| Popular challenge, pool temporarily exhausted by a burst | Queue wait + cold-start for the overflow requests — worse than eager (which never queues), though the autoscaler should narrow this window over time |
| Unpopular/cold challenge, empty pool | Same as lazy's cold-start (Node ~1-1.5s, Python ~1-2s, Java 2-15s) |

The latency profile is **bimodal** rather than uniform — excellent for hot challenges, no better than lazy for cold ones — unlike eager's uniformly-good-if-warm profile or lazy's uniformly-cold-tax profile.

---

## 4. Deferred Eager (lazy trigger, eager-style retention) — Recommended Default

A hybrid: the container isn't created until the **first** Run or Submit click in a session (lazy trigger point), but once created it stays warm and is reused by **both** Run and Submit for as long as the session keeps acting within an idle window (10 min as a placeholder). After 10 minutes with no activity, it's torn down; the next action after that cold-starts fresh again, restarting the cycle.

This combines lazy's cost discipline (no container for sessions that never act) with eager's latency benefit (near-instant on repeat actions), without pooled's cross-user reuse complexity.

### 4.1 How it works

1. User opens the problem. No container exists yet — identical to lazy, zero cost.
2. User clicks Run or Submit for the first time. Container is created on demand (full cold-start paid here, same as lazy).
3. The container stays alive, tracked by a "last activity" timestamp updated on every subsequent Run/Submit.
4. Any further Run or Submit click within the idle window reuses this same warm container — no boot cost, just file-sync + exec.
5. If no activity occurs for the idle-timeout duration (10 min example), the container is torn down. The next action after that restarts from step 2.

### 4.2 Advantages

1. **Zero cost for "opened but never acted" sessions** — same as pure lazy. Eliminates eager's single biggest waste: paying for every problem-open regardless of whether the user ever clicks anything.
2. **Fixes lazy's worst weakness directly.** Only the *first* click in a session pays cold-start cost; every subsequent Run/Submit within the engagement window is near-instant — directly solves the edit-run-edit-run loop latency pain that pure lazy could not.
3. **A much smaller, higher-intent idle-timeout population than eager's.** Eager holds a container for every open problem, including pure browsers who never interact. This model only holds a container for sessions that have already demonstrated intent by clicking at least once — same reaper machinery, applied to a strictly smaller and more deserving population.
4. **Simpler and safer than pooled provisioning.** No per-challenge pool partitioning, no autoscaler, and no cross-user container reuse — so none of pooled's reset-between-untrusted-users security concern (§3.4). The container here is always single-session, single-user, for its entire life.
5. **Strictly dominates both pure models on the dimensions that matter most.** Cost-wise it's ≤ eager (same latency win, delivered to a smaller population that's actually earned it). Latency-wise it's ≥ lazy on every action after the first.

### 4.3 Disadvantages

1. **First click still pays full cold-start.** Java's 2-15s tax on the very first Run or Submit in a session is unavoidable — identical weakness to pure lazy, since nothing is pre-warmed before that click.
2. **Idle-timeout/reaper machinery is still required**, just scoped to time-since-last-action instead of time-since-problem-open — not less code to build, just a smaller, more justified population to run it against.
3. **The "container missing when action fires" edge case still exists at the idle-timeout boundary.** If a user pauses longer than the window (stepped away, distracted) and returns, the next click cold-starts again — same failure shape as eager, just triggered later and less often.
4. **No pre-warming lead time.** Unlike eager, there's no way to know which image to prepare until the first click actually happens — same registry-cache unpredictability as lazy, but only for that one initial click per session.
5. **Doesn't smooth bursty load the way eager does.** Container creation still clusters around whenever users decide to click, not spread out across problem-open events — though this matters less here since it's a smaller, later-triggered population than eager's.

### 4.4 Cost

The cost driver shifts from `(all opened sessions) × idle-timeout × container-cost` (eager) to `(sessions that clicked at least once) × idle-timeout × container-cost` (this model). If, for example, half of all problem-opens never result in a single Run/Submit click — plausible given browsing/reading without acting — this model's cost is roughly **half of eager's tiered-idle-timeout estimate** (§2.3), while still delivering eager's latency benefit to every session that actually engages. Precise numbers need real "click-through rate from open to first action" telemetry, but directionally this strictly improves on eager's cost for the same latency payoff where it matters.

### 4.5 Latency

| Action | Latency |
|---|---|
| First Run or Submit in a session | Full cold-start — Node ~1-1.5s, Python ~1-2s, Java 2-15s (same as lazy) |
| Any subsequent Run/Submit within the idle window | Near-instant (same as eager's best case) |
| Action after the idle window has elapsed | Back to full cold-start (re-triggers the cycle) |

### 4.6 Why this is the recommended default

Cheaper than eager, faster-on-repeats than lazy, simpler and safer than pooled. It's the natural compromise: cost discipline of lazy for casual browsers, latency profile of eager for anyone who actually engages, without pooled's per-challenge partitioning or cross-user reuse risk. Pooled provisioning remains a worthwhile later refinement specifically targeting the *first-click* cold-start this model still doesn't solve (particularly for Java) — but only once real traffic data justifies that added complexity on top of this simpler default.

---

## 5. Side-by-Side Summary

| | Lazy | Eager | Pooled | Deferred Eager (recommended) |
|---|---|---|---|---|
| Cost (200 concurrent users) | Near-zero (~cents-$ total) | ~$1,460-4,390/month depending on idle-timeout tuning | Between lazy and eager; closer to lazy if demand is concentrated on a few popular challenges | Roughly half of eager's tiered cost (or less), scaled by the fraction of opens that never click anything |
| Latency on first click | Full cold-start every time (Java: 2-15s) | Near-instant if still warm; full cold-start if reclaimed | Near-instant for popular challenges with a warm pool member; cold-start for unpopular ones | Full cold-start (Java: 2-15s) — same as lazy |
| Latency on repeated clicks (edit-run loop) | Full cold-start every time — worst fit for this | Near-instant if container persists across the session | Near-instant if the challenge's pool stays populated through the session | Near-instant within the idle window — same as eager's best case |
| Idle-timeout / pool-sizing machinery needed | None | Idle-timeout reaper + activity tracking, applied to all open sessions | Autoscaler reacting to per-challenge demand/queue depth | Idle-timeout reaper + activity tracking, applied only to sessions that have acted at least once |
| "Container missing/exhausted" fallback needed | Never | Yes — whenever idle-timeout reclaims before click | Yes — whenever a pool is exhausted faster than it can grow | Yes — whenever the idle window elapses before the next click |
| Peak load shape | Bursty, clustered around Run/Submit clicks | Spread out, clustered around problem-open events | Smoothed for predictable bursts if pre-scaled; bursty for unpredicted spikes | Bursty, clustered around first-click events — smaller population than eager's |
| Reuse-between-users safety concern | N/A — always fresh | N/A — container is single-session | Real concern — needs destroy-and-replace or a trustworthy reset between different users | N/A — container is single-session, same as eager |
| Operational complexity | Lowest | Moderate | Highest | Moderate — same machinery shape as eager, smaller scope |

## 6. Notes From LeetCode/HackerRank's Approach

Both platforms treat naive per-submission container spawning as a scaling dead end past trivial traffic, and both land on the same shape: async queue → autoscaling warm-container pool → supervisor-enforced sandboxing (cgroups, syscall interception, network lockdown, read-only filesystem, non-root user). The one structural difference that matters for us: their pools are generic per-language judge sandboxes with no per-problem dependency tree, so one pool serves the entire catalog for a language. Our deliberate choice to bake real, challenge-specific dependency trees into images (§4 of `repo-execution-architecture.md`, to support production-like repos) means we can't get that same maximal reuse — our pools are necessarily partitioned per challenge × framework, and the benefit concentrates on whichever challenges are currently popular rather than spreading evenly across the whole catalog.

## 7. Open Decision

Lazy, eager, pooled, and deferred-eager sit on a spectrum of cost-vs-latency-vs-complexity tradeoffs. The right choice — or right *mix* — still depends on data we don't have yet:

1. **Real "opened but never ran" rate** — sets eager's wasted-spend floor, and directly sets how much cheaper deferred-eager is than eager (the gap between "all opens" and "opens that click at least once").
2. **Real time-to-first-Run distribution** — sets how generous the idle-timeout/retention window needs to be (eager, pooled, or deferred-eager) for the latency win to actually materialize most of the time, rather than expiring before the user's next click.
3. **Per-challenge popularity/traffic-concentration distribution** — determines whether pooled provisioning is worth its added operational complexity at all, or whether demand is too spread-out across the catalog for pool hit-rates to be meaningful.

**Needs telemetry before finalizing the exact idle-timeout value**, but the model choice itself doesn't need to wait: **deferred eager (§4) is the recommended default** for all three frameworks — it strictly improves on lazy's repeat-action latency and on eager's wasted spend, without pooled's cross-user reuse risk or per-challenge partitioning complexity. **Pooled provisioning** remains the most promising further upgrade, specifically to address the *first-click* cold-start that deferred-eager still doesn't solve — worth revisiting for **Java** first once traffic data shows enough per-challenge concentration to justify it.
