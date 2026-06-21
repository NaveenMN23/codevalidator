# Design Discussion: Execution Service Architecture (Deferred Eager, Java first)

**Status:** Draft — design discussion, no implementation started.
**Companion to:** `repo-execution-architecture.md`, `execution-tradeoffs-and-timeout.md` (§4 Deferred Eager)
**Scope:** The concrete service-level architecture needed to implement Deferred Eager — the earlier docs settled on the *lifecycle policy* (create on first click, reuse, idle-timeout reap); this doc settles the *service topology* that enforces it, starting with Java/Spring Boot as the first language before extending to Node/Python.

---

## 1. Why a New "Execution Service" Is Needed, Separate From the Main Backend

Deferred Eager requires something to (a) hold Docker access, (b) own a session→container registry, (c) run a background idle-timeout reaper. Giving the main Java backend (auth, problem browsing, business logic) direct access to the Docker socket would meaningfully increase blast radius if that process is ever compromised — it's a privileged capability that should be isolated to a single-purpose process.

**Decision:** A dedicated **Execution Service** owns Docker access, the session registry, and the reaper. The main backend never touches Docker directly — it only orchestrates, consistent with the "backend never execs user code" principle already established in `repo-execution-architecture.md` §6.

---

## 2. Language/Runtime for the Execution Service

| Option | Pros | Cons |
|---|---|---|
| **Python (docker-py + FastAPI)** | `docker-py` is the most mature, ergonomic Docker control SDK (container create/exec/logs/stop all first-class). The work here is inherently I/O-bound (waiting on the Docker API, waiting on `mvn test` to finish) — Python handles this fine. FastAPI gives async HTTP/streaming support with little ceremony. | Second language/runtime alongside the Java backend to operate. |
| **Java (docker-java + Spring Boot)** | Same language as the main backend — one toolchain, shared DTOs/retry patterns possible. | `docker-java` is comparatively clunky and less actively maintained than `docker-py` for the actual hard part of this service (container lifecycle control). |
| **Go** | Best technical fit — Docker's own ecosystem is Go-native; goroutines suit managing many concurrent container handles + a reaper. | Brand-new language/toolchain in the stack for one service — new CI/build/deploy tooling, no existing team footprint. |
| **Node.js (dockerode)** | Reasonable SDK. | Session/container lifecycle management isn't a natural extension of Node's existing role here (UI, challenge apps). |

**Decision: Python + docker-py + FastAPI.** Best SDK maturity for the actual hard problem (Docker control); the operational cost of a second language is acceptable given the Docker-socket boundary already argues for a separate process regardless of language choice.

---

## 3. Backend ↔ Execution Service Transport, and the Thread-Starvation Concern

**Initial framing:** sync HTTP (request/response, blocks until done) vs. async via a queue (RabbitMQ-style, fire-and-forget + callback).

**Container affinity rules out a naive queue.** Deferred Eager means a container persists across multiple separate requests over time (Run → Run → Submit) and lives on one specific Docker host. An anonymous worker-pool-behind-a-queue model (today's grading pattern) can't honor this without building session-affinity routing on top of the queue anyway — defeating much of the simplicity a queue would otherwise offer. This pushes toward **direct, addressable calls to the Execution Service**, at least for Run. (Submit's async-tolerant nature is a separate, not-yet-settled question — see §5.)

**Thread-starvation concern (raised and resolved):** if the backend (Spring/Tomcat) makes a *blocking* HTTP call to the Execution Service and a Run takes 1–15s (Java cold start), that Tomcat request thread is held for the whole duration. With a bounded thread pool (~200 default), enough concurrent Run traffic would starve unrelated requests (e.g. "view profile," contest endpoints) — a real risk even at the docs' own reference scale (~200 concurrent users).

**Resolution:** "blocking vs non-blocking I/O" is a separate axis from "sync vs async transport." The fix is to make the backend's *wait* non-blocking regardless of call shape: use Spring's reactive `WebClient` (not blocking `RestTemplate`) for the backend→Execution Service call, with the controller returning `Mono<...>`/`DeferredResult`. Spring MVC supports this via async servlet dispatch without requiring a full WebFlux rewrite — only this call path needs to be non-blocking. The Tomcat thread is released back to the pool the instant the call is issued, and only briefly reclaimed when the response arrives.

**Decision:** Backend→Execution Service calls use non-blocking I/O (reactive `WebClient`), regardless of which output-delivery model is chosen below.

---

## 4. Output Delivery for Run: Buffered vs. Streamed

**Buffered:** backend awaits the full result non-blockingly (`Mono`), returns one response with complete stdout/stderr once the command finishes. Simple; matches today's grading result shape; no streaming infra. No live terminal output.

**Streamed — mechanism, two layers:**

1. **Continuous output out of the container:** `docker-py`'s `container.logs(stream=True, follow=True)` (or `attach`) yields output chunks as the process produces them, not after exit. FastAPI wraps this generator in a `StreamingResponse` — the Execution Service's HTTP response is itself a live, growing stream.

2. **Relaying that stream to the browser without blocking a thread** — two viable paths:

   - **Path A — Full reactive relay.** `WebClient` consumes the Execution Service's streaming response as a `Flux<String>` (chunks arrive via async I/O completion events). The controller exposes that same `Flux` onward as SSE (`Flux<ServerSentEvent<String>>`) — supported in Spring MVC without converting the whole app to WebFlux.
     - *Advantages over Path B:* genuine backpressure (a slow browser naturally throttles how fast Docker logs get read, vs. Path B's blocking loop having no built-in throttle); far better resource efficiency at high concurrency (a small Netty event-loop pool multiplexes many streams vs. Path B's one-real-OS-thread-per-stream, ~1MB stack each); no pool-sizing guesswork (Path B needs a pre-sized executor for "max concurrent active streams" — too small queues/rejects, too big wastes threads; Path A's concurrency is bounded by memory/sockets, not a fixed thread count); composable timeouts/retries/merges via Reactor operators instead of hand-rolled imperative logic; consistent non-blocking-ness end-to-end since the Execution Service (FastAPI) is already async — Path B just relocates the blocking-thread "island" rather than removing it.
     - *Costs:* steeper learning curve, harsher debugging (reactive stack traces), real risk of accidentally calling something blocking inside a reactive chain and silently reintroducing the original problem. These costs are real now; the advantages are mostly latent until concurrency is much higher than the current few-hundred-user scale.

   - **Path B — `SseEmitter` + a dedicated bounded thread pool.** Controller returns immediately (Tomcat thread freed); a separate thread from a small, app-controlled executor (sized for "max concurrent active Run streams," *not* Tomcat's pool) does a blocking read loop over the Docker log stream and pushes chunks into the emitter. Still blocking I/O under the hood, but quarantined to a pool sized deliberately — can't starve unrelated endpoints. Much simpler to write/debug than Path A; the resource-efficiency gap vs. Path A is unlikely to matter at hundreds (not thousands) of concurrent sessions.

**Status: not yet decided.** Options on the table, in order of build simplicity:
1. Skip streaming for v1 — buffered response only.
2. `SseEmitter` + dedicated thread pool (recommended if streaming is wanted now).
3. Full reactive relay (Path A) — defer until concurrency genuinely demands it.

---

## 5. Deep Mechanics: How Path A and Path B Actually Work

Both paths solve the same problem — relay a live stream from the Execution Service to the
browser without letting Tomcat's main thread pool get exhausted — but they achieve it through
fundamentally different concurrency models. This section traces each one mechanically, step by
step, for a single "user clicks Run" request.

### 5.1 Path A — Full Reactive Relay (WebFlux / Reactor Netty Event Loop)

**The event loop model, in general.** Reactor Netty (the HTTP engine behind Spring's reactive
`WebClient` and WebFlux) runs a small, fixed number of threads — by default
`Runtime.getRuntime().availableProcessors()`, so e.g. 8 threads on an 8-core node — called the
*event loop group* (`reactor-http-nio-1` through `-N`). This is the same architectural pattern
as Node.js's single-threaded event loop, generalized to N threads instead of 1. Each event loop
thread runs a tight loop registered with the OS's I/O multiplexer (`epoll` on Linux, `kqueue` on
macOS, an IOCP-backed equivalent via Netty's NIO transport on Windows). Sockets are registered
for "interest" in events (readable, writable); the OS tells the event loop thread which sockets
are *actually* ready, and the thread only does work for those — it never sits there waiting on
an idle connection. A single event loop thread can therefore service thousands of concurrent
connections, because at any given instant the overwhelming majority of them are idle (no bytes
to read, nothing queued to write) and cost the thread nothing.

**The critical rule this model imposes:** whatever code runs *on* an event loop thread must be
non-blocking and fast. If a callback does something blocking (a JDBC call, `Thread.sleep`, a
blocking `RestTemplate` call), it stalls that one event loop thread for the duration — and
because that same thread is multiplexing potentially hundreds of *other* unrelated connections,
all of them stall too. This is the single most common way WebFlux deployments go wrong in
practice, and it's the concrete shape of the "cost" flagged in §4: it's easy to accidentally
introduce a blocking call deep in a reactive chain and silently reintroduce the exact
thread-starvation problem this whole design is trying to avoid — except now it's harder to
spot, because the symptom (many unrelated requests slowing down) doesn't obviously point back
to the one blocking call causing it.

**Walking through a Run request under Path A:**

1. Browser opens a connection to the backend's Run endpoint, requesting an SSE stream.
2. The Spring WebFlux controller method returns `Flux<ServerSentEvent<String>>` immediately —
   no thread is held waiting; returning a `Flux` just describes the pipeline, it doesn't execute
   anything yet (Reactor publishers are cold/lazy until subscribed).
3. WebFlux's HTTP-handling layer *subscribes* to that `Flux` on behalf of the browser's
   connection. Subscribing is what actually triggers Reactor Netty to open an outbound
   connection to the Execution Service and issue the HTTP request for `WebClient.get(...).retrieve().bodyToFlux(String.class)`.
4. As the Execution Service (FastAPI) streams chunks of Docker's stdout/stderr, those bytes
   arrive on the OS socket. The event loop thread is woken by the OS multiplexer ("this socket
   has data"), reads the available bytes in one non-blocking call, decodes them per the
   configured codec, and emits each chunk downstream via `onNext` — all within that single,
   brief callback invocation. The thread is not "waiting" between chunks; it's free to service
   other connections' ready sockets in the meantime, and gets re-invoked the next time *this*
   socket has more data.
5. Each emitted chunk flows through the reactive pipeline (any `.map()`/`.filter()` operators
   applied) and reaches the outbound side, where it's written as an SSE event to the browser's
   connection — again as a non-blocking write on an event loop thread.
6. **Backpressure**, end to end: the browser's TCP receive window and how fast the browser-side
   reader actually consumes data ultimately bounds how much the *subscriber* requests
   (`request(n)` in Reactive Streams terms). When demand is exhausted, Reactor Netty stops
   issuing reads on the inbound channel (`channel.config().setAutoRead(false)`), which lets that
   socket's receive buffer fill, which — via ordinary TCP flow control — causes the Execution
   Service's *send* to start blocking/slowing, which (only if the Execution Service's own log-read
   loop is itself async and respects that, e.g. an `asyncio` generator awaiting on the socket
   write) naturally throttles how fast Docker logs get pulled in the first place. This is real,
   but it's coarse — SSE over HTTP has no explicit per-message backpressure protocol the way some
   WebSocket subprotocols do; what you get is TCP-level flow control propagated through Netty's
   auto-read toggling, which is adequate to prevent unbounded buffering but isn't a fine-grained
   credit system.
7. Thread accounting at the end of all this: the *entire* Run request, from connection open to
   stream completion, never occupies a dedicated thread for its duration. The 8 (or so) event
   loop threads are shared across every concurrent connection on the node — Run streams, regular
   API traffic if WebFlux were used app-wide, everything — each only consuming thread time for
   the brief instants it has actual I/O work to do.

### 5.2 Path B — "Island of Threads" (`SseEmitter` + Dedicated Bounded Executor)

**The model, in general.** This path keeps Tomcat's default thread-per-request world intact for
the rest of the application, and carves out one deliberately isolated, separately-sized pool of
threads just for the blocking work of relaying a Run stream. The word "island" is apt: it's a
self-contained pocket of blocking concurrency, walled off so that if it fills up, nothing outside
it is affected.

**Walking through a Run request under Path B:**

1. Browser opens a connection to the backend's Run endpoint.
2. The controller method returns an `SseEmitter`. Spring MVC recognizes this return type and,
   under the hood, calls the Servlet 3.0+ `request.startAsync()` mechanism. This is the load-bearing
   trick: it tells Tomcat "this request isn't done, but don't hold one of your fixed worker
   threads open for it." Tomcat's NIO connector has a separate, lightweight `Poller` component
   that keeps watching the underlying socket for the async context, decoupled from the bounded
   worker-thread pool that handles "view profile" and everything else. The Tomcat request thread
   that initially accepted this request returns to the pool almost immediately.
3. The controller submits a task to a dedicated `ExecutorService` — e.g. a fixed pool of size
   50, sized deliberately for "expected max concurrent active Run streams," entirely separate
   from Tomcat's own executor. This is the actual "island": its capacity is a hard, known number
   you chose, not shared with anything else.
4. A thread from that pool now does old-fashioned blocking work: it opens an HTTP connection to
   the Execution Service (a plain blocking client is fine here — there's no reason to use a
   non-blocking client inside a thread that's dedicated to blocking work anyway), and loops
   reading the streaming response body chunk by chunk via a blocking `InputStream.read()`. For
   each chunk read, it calls `emitter.send(chunk)` to push the data out over the still-open async
   connection from step 2. This thread is genuinely blocked, on and off, for the entire duration
   of the Run — that's the cost of this model: **one real OS thread per concurrently active Run
   stream**, each with its own ~1MB default stack (tunable via `-Xss`) and its own scheduling
   overhead.
5. When the underlying stream ends, the thread calls `emitter.complete()`, which finalizes the
   SSE connection and lets Tomcat clean it up.
6. **What happens at saturation:** if all 50 threads in the dedicated pool are busy and a 51st
   Run request comes in, the task queues (if the `ThreadPoolExecutor` is configured with a
   bounded queue) until a thread frees up, or — if the queue is also full — gets rejected
   immediately per whatever `RejectedExecutionHandler` is configured (e.g. `AbortPolicy` throws
   and the controller can translate that into an honest "server busy, try again" response to the
   user, rather than letting requests pile up unboundedly in memory). Crucially, **none of this
   touches Tomcat's main pool** — "view profile" and other ordinary endpoints keep being served
   normally by their own threads throughout, even while the Run-island is completely saturated.
7. Thread accounting: unlike Path A, thread cost here scales linearly with concurrently *active*
   Run streams (not total connections) — 50 active streams means 50 real threads occupied for
   their full duration, full stop. The isolation guarantee is real and simple to reason about;
   the cost is that this pool's size is a real ceiling you have to pick and tune, and getting it
   wrong in either direction has a direct, visible failure mode (rejections if too small, wasted
   idle thread/memory footprint if too large).

### 5.3 Side-by-Side of the Two Mechanisms

| | Path A (Reactor event loop) | Path B (dedicated thread island) |
|---|---|---|
| Threads used per concurrent Run stream | ~0 dedicated — shared across a small fixed event-loop pool (≈ CPU core count) | 1 real OS thread, blocked for the stream's full duration |
| How "isolation from Tomcat" is achieved | Architectural — there's no thread-per-connection model to begin with | Explicit — a separately bounded `ExecutorService`, walled off from Tomcat's pool |
| Backpressure | Real, via Reactive Streams demand signals propagated through TCP flow control | None built in — a slow client just means the thread blocks longer on `emitter.send()`/socket writes; no mechanism throttles the upstream Docker log read |
| Saturation behavior | Bounded by memory/open sockets, not a fixed thread count — degrades gradually | Hard ceiling at pool size — clean, explicit reject/queue behavior once full |
| Risk of reintroducing the original problem | Real — any accidental blocking call inside the reactive chain stalls an event loop thread and everything else sharing it | Low — the blocking is intentional and contained by design; it can only ever exhaust its own pool |
| Code complexity / debuggability | Higher — Reactor operator chains, less familiar stack traces | Lower — plain imperative blocking code, just run on a different pool than usual |

---

## 6. Virtual Threads (Java 21) as an Alternative to the Path A/B Fork

**Question raised:** is there something better than an event loop (Path A)? And separately,
would Kafka help with the container-affinity/routing problem from §3?

### 6.1 Virtual threads, mechanically

Java 21 (already this stack's version, per `pom.xml`) ships Project Loom's virtual threads.
The JVM runs many lightweight, heap-allocated **virtual threads** multiplexed onto a small pool
of real OS **carrier threads** (sized ≈ CPU core count by default — the same order of magnitude
as Reactor Netty's event-loop group in Path A). Code on a virtual thread looks and behaves like
completely ordinary blocking Java. When it calls a blocking operation the JDK has adapted to be
virtual-thread-aware (modern `java.net.http.HttpClient`, NIO sockets, many JDBC drivers), the
runtime **unmounts** the virtual thread — saves its continuation state — and frees the carrier
to run other virtual threads. When the blocking call completes, the virtual thread **remounts**
onto any free carrier and resumes with its full call stack intact, exactly as if it had been
sitting there the whole time.

The non-obvious part: this isn't a different I/O strategy than the event loop, it's **the same
`epoll`/`kqueue`-based non-blocking I/O underneath**, with the JVM hiding the callback machinery
so application code never has to be written in reactive style. A small set of internal JDK
poller threads watch the file descriptors and unpark the right virtual thread when data is ready
— conceptually the same trick Reactor Netty's event loop performs, just exposed to the programmer
as `inputStream.read()` instead of `.onNext()`.

Enabling it: one Spring Boot property, `spring.threads.virtual.enabled=true`. Every servlet
request then runs on a virtual thread instead of a pooled platform thread.

### 6.2 What this collapses

- **§3's need for reactive `WebClient` mostly disappears.** A plain blocking HTTP call to the
  Execution Service, made from a virtual thread, parks cheaply instead of holding a scarce
  platform thread — no `Mono`/reactive chain required for that hop.
- **§4's Path A/B fork mostly dissolves, in Path B's favor, not Path A's.** Path B's
  `startAsync()`/dedicated-executor dance exists specifically because Tomcat's *own* request
  thread is normally a scarce platform thread. Once Tomcat itself runs on virtual threads, the
  original request-handling thread is already cheap — there's no need to free it and hand off to
  a separate, hand-sized executor. A plain synchronous controller method that blocks for the
  entire Run duration (reading Docker logs in a loop, writing to the response as it goes, e.g.
  via `StreamingResponseBody`) costs one virtual thread, not one platform thread. **Net effect:
  plain, boring, synchronous Java throughout the Run/Submit path — no Reactor, no `WebClient`, no
  hand-built bounded executor.**
- **Unaffected:** the Execution Service stays Python/FastAPI (§2) — virtual threads are JVM-only.
  Separately worth noting: `docker-py` itself is a blocking SDK, so FastAPI handlers calling it
  need to run those calls off FastAPI's own event loop (FastAPI does this automatically for `def`
  endpoints via its internal thread pool, or explicit `run_in_threadpool`/`asyncio.to_thread`) —
  the Python side has its own version of this same blocking-stalls-the-loop problem, a separate
  decision from this one.
- **Unaffected:** the container-affinity/registry reasoning in §3 for why a naive queue doesn't
  work — that's about routing to the correct Docker host, not backend thread concurrency.

### 6.3 The pinning caveat

A virtual thread **cannot** unmount while inside a `synchronized` block/method, or certain native
(JNI) calls — lock ownership and native stack frames are tied to the real OS thread in JDK 21's
implementation, not portable to a suspended continuation. Hitting this in the hot path silently
reintroduces the exact thread-exhaustion problem this whole design avoids, just harder to spot.
JDK 21 ships `-Djdk.tracePinnedThreads` to surface this during development. JDK 24 (JEP 491)
fixed `synchronized` pinning for most cases — **not backported to 21**. Mitigation: prefer
`ReentrantLock` over `synchronized` in anything on the Run/Submit hot path (the JDK team's own
recommendation), and audit `platform-backend_service` for existing `synchronized` usage before
relying on this — a quick grep, not yet done as of this writing.

### 6.4 Kafka, evaluated as an alternative to §3's registry/routing approach — rejected

- Kafka consumer-group partition assignment is *stickier* than RabbitMQ's competing-consumers
  model (partitioning a topic by `session_id` usually keeps a session's messages on the same
  consumer) — but every rebalance (consumer scale up/down, crash, restart — normal operational
  events) reassigns partitions, which can land a session's traffic on a consumer without its warm
  container. Same failure mode as the plain-queue problem in §3, just less frequent.
- Kafka is architected for durable, replayable, async event logs, not low-latency interactive
  request/response. Getting a result back to the original caller means building a reply channel
  on top (results topic + correlation ID + poll/subscribe) — solving a problem a direct call
  already avoids for free.
- **Conclusion: do not introduce Kafka.** Real operational cost (cluster, partition management)
  for only a partial fix to the affinity problem, and a worse fit than even RabbitMQ for the
  interactive-response shape Run/Submit need.

### 6.5 Quantitative Comparison

Figures below are representative orders of magnitude (JDK defaults, typical commodity hardware) —
not a benchmark of this specific service; exact numbers depend on JVM version, OS, and tuning.

| | Platform thread (Path B) | Virtual thread (§6 proposal) | Reactor event loop (Path A) |
|---|---|---|---|
| Memory cost per unit of concurrency | ~1MB default stack each (`-Xss`, fixed at creation) | Starts at a few hundred bytes, grows on the heap as needed | ~tens of KB per connection (socket buffers + Netty channel state) — no per-unit *thread* at all |
| Practical max concurrent "in-flight" units on one node | Low thousands before scheduler/memory pressure degrades throughput (e.g. 5,000 threads ≈ 5GB in stacks alone, before counting scheduling overhead) | Demonstrated in the millions in JDK/Loom benchmarks (JEP 444's own examples target ~1,000,000+ concurrently-parked virtual threads on commodity hardware) | Tens of thousands of connections is routine — bounded by memory/file descriptors, not threads |
| Number of real OS threads actually running concurrency | 1 per active unit (e.g. 1,000 active Run streams = 1,000 OS threads) | ≈ CPU core count (carrier pool), regardless of how many virtual threads are logically "in flight" | ≈ CPU core count (event-loop group), regardless of connection count |
| Context-switch / mount cost | Full OS context switch (~1–10µs, kernel transition, possible TLB/cache effects) | Continuation save/restore in user space scheduled via a `ForkJoinPool` — no kernel transition, generally sub-microsecond and cheaper than an OS switch | N/A — no per-task switch; a callback either runs to completion or doesn't run yet |
| Programming model | Plain blocking code | Plain blocking code (identical to Path B) | Reactive (`Flux`/`Mono`, composed operators) |
| Stack traces / debuggability | Normal, full call chain | Normal, full call chain (same as Path B) | Often shows scheduler/operator-chain frames, not the business-logic call chain, unless debug hooks are explicitly enabled |
| Library compatibility | Any blocking library works, unmodified | Any blocking library works, unmodified — *unless* it uses `synchronized` internally (pinning, §6.3) | Requires every component in the chain to be non-blocking-aware (e.g. R2DBC instead of JPA) to get the full benefit |
| Known failure mode | Pool exhaustion at a known, tunable ceiling | Pinning inside `synchronized`/native calls (JDK 21; fixed in 24) | Accidental blocking call inside the reactive chain stalls an event-loop thread and everything sharing it |

### 6.6 Why virtual threads look like the better fit for this specific app

1. **Already on the required JDK version** (21) — zero new infrastructure, one config line.
2. **The existing/planned backend code is full of ordinary blocking calls** (Spring Data JPA,
   `@Retryable`/Resilience4j-wrapped service calls per `CLAUDE.md`) — virtual threads make *all*
   of that cheap to run concurrently without rewriting any of it. The event-loop model only pays
   off if you also migrate the data layer to a reactive driver (R2DBC) — a large, disruptive
   lift for endpoints that don't need it.
3. **Strictly simpler code and debugging** than Path A, while matching Path B's simplicity and
   beating its per-stream memory/thread cost by roughly three orders of magnitude (per §6.5).
4. The one real cost — the `synchronized`-pinning caveat — is a known, auditable, fixable
   property of the current codebase, not an open-ended risk.

**Status:** recommended direction for §3 and §4, pending the `synchronized`-usage audit and
explicit confirmation before it's treated as final.

---

## 7. Open Decisions Still Outstanding

1. **Virtual threads vs. reactive `WebClient` vs. both** (§6) — recommended: virtual threads
   everywhere on the backend, replacing the §3/§4 reactive approach with plain blocking code.
   Pending: `synchronized`-usage audit of `platform-backend_service`, and explicit confirmation.
2. **Output delivery for Run** (buffered response vs. streamed via blocking read loop + virtual
   threads, per §6.2) — pending decision; with virtual threads adopted, streaming has a much
   lower cost than originally scoped under Path A/B, so this is somewhat less urgent to settle.
3. **Submit path:** does it reuse the session's warm container (same affinity problem as Run), or stay fully async/ephemeral as it is today? Not yet discussed.
4. **Session registry persistence:** in-memory in the Execution Service (disposable — a restart is equivalent to an idle-timeout reap) vs. backed by Redis/Postgres. Leaning in-memory for a single-node v1, not yet confirmed.
5. **Single execution node vs. multi-node session routing.** Single-node sidesteps the container-affinity routing problem entirely; multi-node requires a shared registry (e.g. Redis: session_id → node) from day one. Leaning single-node for v1 (matches current scale and the design docs' own "don't build speculatively" stance), not yet confirmed.
6. **Idle-timeout value** — design docs flag this as needing real telemetry; placeholder 10min.
7. **File sync mechanism** (editor → container) — push-on-autosave vs. sync-at-Run-time. Not yet discussed.
