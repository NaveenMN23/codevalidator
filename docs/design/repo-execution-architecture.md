# Design Discussion: Repo Viewing & Execution Architecture

**Status:** Draft — design discussion, no implementation started.
**Scope:** How a problem's repo is fetched, viewed, and executed for the user, across multiple language frameworks.

---

## 1. Background / Why This Came Up

The original platform (`platform-backend` + old `Workspace.tsx`) loads a challenge repo from S3 as a zip, unzips it client-side, and mounts it into a browser-native **WebContainer** (StackBlitz WASM Node.js runtime). `npm install` and test execution both happen entirely in the browser. This was a deliberate choice (see `ARCHITECTURE.md`, Pillar 2: "Browser-Native Execution") to keep server load down during the dev loop.

This design is being revisited because of new requirements:

- The platform will offer **multiple frameworks**: Spring Boot/Java, Node.js, Python/FastAPI — extensible to more in the future.
- Challenge repos will be **production-like**, with real, non-trivial dependency trees (not toy boilerplate).
- Test execution is split: roughly **20% of generated test cases run on Run/Submit from the client side**, the remaining ~80% run server-side.
- A downstream **evaluator service** (currently a blackbox) runs after a successful submission and will likely need the user's code diff.
- A core goal is **low latency / smooth experience** when a user opens a problem.

---

## 2. Key Architectural Fork: WebContainer Is Node.js-Only

WebContainer is a WASM-compiled Node.js runtime. It cannot run:
- A JVM (Spring Boot) — no in-browser execution path exists.
- A real Python interpreter with native sockets (Pyodide exists but `uvicorn`'s ASGI networking and compiled wheels like `pydantic-core` aren't reliably WASM-compatible for production-like FastAPI apps).

**Conclusion:** supporting Java and Python at production fidelity requires **server-side container execution**. To avoid maintaining two completely different execution/latency models (WebContainer for Node, server containers for Java/Python), the platform should adopt **server-side containers as the uniform execution model for all frameworks**, including Node.js.

---

## 3. Two Separate Artifacts (Do Not Conflate)

| Artifact | Purpose | Contents | Where it lives | Who fetches it |
|---|---|---|---|---|
| **Source repo (S3 zip)** | Browser-side viewing/editing | Source files, visible tests, README, manifest. **No dependencies.** | S3 / CDN | Browser, directly (presigned URL) |
| **Pre-baked Docker image** | Server-side execution | Source structure + dependencies already installed (`node_modules`, `.m2` cache / built jar, Python venv/wheels) | Container registry | Worker/execution nodes only, never the browser |

Baking dependencies into the image does **not** increase the size of the browser-facing repo artifact — if anything it shrinks it, since the browser no longer needs anything related to dependency installation. The size growth instead happens in the container registry, as a one-time, build-time cost (paid when a challenge is published or its dependencies change), not a per-user/per-request cost.

---

## 4. Dependency Strategy: Pre-Baked Images, Not Session-Time Installs

**Decision direction:** install dependencies once, at challenge **publish time**, into a Docker image layer — not per user session.

- Node.js: `COPY package*.json . && RUN npm install` baked into the image.
- Python/FastAPI: `COPY requirements.txt . && RUN pip install -r requirements.txt` baked into the image.
- Spring Boot: `COPY pom.xml . && RUN mvn dependency:go-offline` (or full `mvn package`) baked into the image.

This mirrors a pattern the repo already uses one level up: `platform-codegen/generator/engine.py` already does "strip + zip once at publish time" for source code (per-scenario `@strip-target` stripping). Image-baking extends the same principle to dependencies.

A build pipeline step is needed: triggered whenever a challenge's `package.json` / `requirements.txt` / `pom.xml` changes, it builds and pushes an image per challenge × language/framework variant. Worker nodes need the image pulled/cached ahead of demand, or the first user pays a cold-pull penalty.

### Rough latency numbers (pre-baked image, warm registry cache on the node)

| Framework | Image pull (warm cache) | Process/runtime boot | Dominant remaining cost |
|---|---|---|---|
| Node.js / Express | ~0-1s | 100-500ms | negligible |
| Python / FastAPI | ~0-1s | 300ms-1s | negligible |
| Spring Boot / Java | ~0-1s | **2-8s** typical, up to 10-15s with heavier starters (security, data-jpa) | JVM classloading + Spring's reflection-based bean wiring — doesn't go away with caching; a warm JVM pool would be the next lever |

If the image is **not** cached on the serving node: add 2-10s for cold image pull, regardless of framework. This makes node-level image pre-warming / a local registry mirror important independent of which framework.

### Rejected/superseded approach: live install per session (for reference)
Originally considered shipping `node_modules` in the artifact (Option A) or installing live per session (Option B) for the Node-only WebContainer model:
- Live `npm install` per session: ~10-30s for small trees, 1-3min+ for production-scale trees.
- Shipping `node_modules` in a zip: bottlenecked not by bandwidth but by WebContainer's per-file `mount()` write overhead across thousands of small files (10-30s+ observed pattern). A binary snapshot format (`@webcontainer/snapshot`) exists to mitigate this but needs a spike to verify against our SDK version.
- **Both superseded** by the pre-baked-image approach once server-side containers became the direction, since install cost becomes a one-time publish-time cost rather than a per-session cost.

---

## 5. End-to-End Flow: User Opens a Problem

1. **User clicks the problem.**
   Browser calls backend (e.g. `GET /api/v1/problems/{id}`) → backend returns metadata + a **presigned S3 URL** for the source-only artifact. Browser fetches directly from S3 (not proxied through the backend, to minimize hops/latency), unzips, renders file tree + Monaco editor.

2. **A container session gets provisioned.** Open question, two options:
   - **Eager**: container starts (from the pre-baked image) as soon as the problem opens, while the user is still reading the problem statement. Backend hands the browser a session handle (container ID / websocket endpoint). By the time the user clicks Run, the container is likely already warm.
     - Tradeoff: pays for a running container per open session even if Run is never clicked → needs an idle-timeout/cleanup policy.
   - **Lazy**: container only starts on first Run click. Simpler, but the user eats full container-start latency at that moment instead of it being hidden.
   - **Leaning eager**, given pre-baked images make startup cheap for Node/Python and the Spring Boot JVM tax is exactly the kind of latency you want to hide behind "user is reading the problem statement."

3. **User edits code** in the browser (Monaco editor). Edits exist only in the browser until synced — **not yet designed**: push-on-autosave-tick (similar cadence to existing 2s draft autosave) vs. sync-only-at-Run. This is the next open design item.

4. **User clicks Run.**
   - Backend (or sync layer) pushes the current edited files into the container's filesystem.
   - Container executes the visible-test subset (~20%).
   - Output streams back to the browser terminal pane.

5. **User clicks Submit.**
   - Full file set is sent to the backend, queued (RabbitMQ, same as the existing `platform-workers` pattern) for the remaining ~80% test execution in an isolated grading container.
   - On a passing grade, the blackbox evaluator service is invoked downstream.

---

## 6. Security & Scalability Properties (Confirmed Design Intent)

All execution of user-submitted code happens **inside the container**, never on the backend process itself. The backend only orchestrates: push files in, instruct execution, stream/collect results out. The backend never `exec`s or interprets user code directly.

This gives:
- **Isolation**: user code can't reach backend memory, other users' containers, or platform infra — especially when run network-disabled and resource-capped (same `DOCKER_MEM_LIMIT` / `DOCKER_TIMEOUT_SECONDS` pattern `platform-workers` already uses for grading).
- **Disposability**: containers are ephemeral/replaceable — a hung or crashed container is destroyed and a fresh one spun up from the same image, no shared state to corrupt.
- **Crash containment**: a user's broken or malicious code can only take down its own container, bounded by timeout.

This extends the isolation model `platform-workers` already applies to grading (Submit path) to the Run path as well, which previously had zero backend exposure (it ran fully in-browser) but also zero multi-framework support.

**Open implication:** Run and Submit may now both spin up containers, roughly doubling orchestration load per session compared to today (where Run was free, client-side). Not yet decided: does a session's Run container get reused for its later Submit, or are Run and Submit always independent ephemeral containers (as grading already is today)?

---

## 7. Diff for the Evaluator Service

Because the backend (not the container) is the layer that pushes user files into the container, the backend already has full visibility into the user's code **before** the container ever touches it. Computing a diff is a backend-side operation on data it already holds — it does not require inspecting the container's filesystem or process state after execution.

This is actually an improvement over the old WebContainer model, where the backend only saw user code once, at Submit time (a one-shot flattened file map). Under continuous sync (per item 5 above), the backend can have visibility into every intermediate version, not just the final submission.

**Deferred questions (explicitly not resolved yet — "we will come to that later"):**
- Diff against what baseline — original boilerplate (showing "what the user changed to fix it") vs. previous submission (incremental diff between attempts)?
- Does the diff get computed/stored only at Submit time, or does the evaluator want intermediate diffs too?
- Current safe default discussed: compute the diff against the original boilerplate at Submit time, store alongside the `submissions` row (or its S3-backed content), and let the evaluator pull it when invoked — avoids assuming things about the still-blackbox evaluator.

---

## 8. Open Design Items (Not Yet Resolved)

1. **File sync mechanism**: how live edits reach the running container (push-on-autosave vs. sync-at-Run-time vs. something else), and how to avoid a sync round-trip on every keystroke.
2. **Eager vs. lazy container provisioning**, and the idle-timeout/cleanup policy if eager.
3. **Run vs. Submit container reuse**: same container instance per session, or always independent ephemeral containers.
4. **Evaluator service contract**: full repo + diff, or diff only; synchronous invocation by the worker vs. its own queue; what `submissions` needs to persist (e.g. S3 pointer vs. inline content) for the evaluator to run later without original request context.
5. **WebContainer binary snapshot spike** — no longer required if server-side containers are adopted uniformly, but noted here in case Node.js is ever special-cased back to client-side execution.
6. **Build pipeline for per-challenge images**: trigger conditions (dependency file changes), registry layout, and node-level pre-warming/caching strategy to avoid cold image pulls.
