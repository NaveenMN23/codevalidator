# Sandbox Image Requirements for Codegen

**Status:** Findings from a live debugging session testing the Fargate run/submit flow against
real AWS. Written as a spec the codegen team can build against — intentionally independent of
`platform-execution_service`, since that service reflects the old local-Docker-daemon execution
model and is being restructured.

---

## 1. Investigation Summary

Goal was to validate the full chain: backend reads a problem's `ecr_image_uri` → spawns a Fargate
task from it → backend sends user code to it → gets results back. Walking through real AWS, in
order:

1. **`RunTaskRequest` had no `taskDefinition` set.** `ExecutionService.spawnAndRegister()` called
   `ecs:RunTask` without specifying which task definition to run — a required field. Fixed by
   adding `resolveTaskDefinition(ecrImageUri)`, which registers (or reuses, if already registered)
   an ECS task definition whose container image is that exact `ecrImageUri`, keyed by a hash of
   the URI. This was necessary because **ECS has no way to override a container's image at
   `RunTask` time** — only command/env/cpu/memory can be overridden; the image is fixed when a
   task definition is registered.

2. **Execution role lacked `logs:CreateLogGroup`.** The task definition sets
   `awslogs-create-group: true`, but the standard `AmazonECSTaskExecutionRolePolicy` managed
   policy only grants `CreateLogStream`/`PutLogEvents`, not `CreateLogGroup`. First real task
   failed immediately with `AccessDeniedException`. Fixed via an inline policy on the execution
   role.

3. **A test problem's `ecr_image_uri` was a bare digest** (`sha256:9e1c726...`), not a full image
   reference. `docker pull` interpreted it as a Docker Hub reference
   (`docker.io/library/sha256:...`) and failed with `pull access denied`. **`ecr_image_uri` must
   always be a complete, pullable reference**, not just a digest fragment.

4. **A real, valid image (`under_study/test_repo:ticket-booking-easy-create-booking-2`) still
   failed** — the ECS task started, then immediately stopped (`Essential container in task
   exited`), with **0 bytes** logged to CloudWatch. `docker inspect` on the pulled image showed:
   ```
   Entrypoint: [/usr/local/bin/mvn-entrypoint.sh]
   Cmd: [mvn]
   ```
   This is the **stock, unmodified default of the official `maven` base image** — meaning
   whatever build produced this image never overrode `CMD`. Running bare `mvn` with no goal/phase
   fails almost instantly with a usage error, which explains both the immediate stop and the
   near-zero log output (the container exited before the log driver could flush anything).

   **Root cause:** the image only had dependencies pre-baked — it never got a persistent listener
   process added on top, nor a `CMD` override to run one. See §2 for why that listener is
   required, not optional.

5. **Side findings, also relevant to codegen's build/push step:**
   - The ECS cluster (`ap-southeast-2`) and this image's ECR repo (`us-east-1`) were in different
     regions. Cross-region pulls work, but add real latency on **every** cold start — Fargate has
     no cross-task image-layer cache, so this cost repeats for every new task, not just once.
     **The ECR repo must be in the same region as the ECS cluster.**
   - Images observed were 68–466MB — reasonable, not bloated. The slowness seen pulling them to a
     local laptop was dominated by general-internet + cross-region distance, not image size or a
     same-region Fargate pull (estimated same-region pull + cold start: ~30-60s total, matching
     the platform's documented cold-start budget).
   - `under_study/test_repo` is **one shared ECR repository holding multiple problems,
     distinguished only by tag**. This works functionally (the backend treats `ecr_image_uri` as
     an opaque string), but doesn't match this platform's documented convention of one ECR
     repository *per problem*. Worth deciding deliberately either way (see §4).
   - `platform-codegen` (this repo's actual codegen service) currently has **no Docker build/push
     code and no direct database write path** — confirmed by searching its source. Whatever
     produced the test images used in this investigation was not this service. The requirements
     below describe the target contract for whatever does end up building these images.
     *(Update: this ended up being `admin-backend`'s `DockerImageService`, not `platform-codegen`
     — see §4.)*

---

## 2. Required Image Contract

This is the part that actually matters: **the container's main process must be a long-lived HTTP
server, not a one-shot test run.**

### Why a persistent server, not "run tests and exit"

The code being tested doesn't exist when the image is built — it's whatever the user has typed
into the editor by the time they click Run, which could be minutes or hours later, and could
happen multiple times (Run, then edit more, then Run again, then Submit) within one session.
Fargate gives no way to inject files into an already-running task after `RunTask` — there's no
"docker cp" equivalent over the ECS API. So the only way the backend can get the user's *current*
code into an already-running container is for that container to be listening for it.

### The HTTP contract the backend depends on

The backend (`ExecutionService.forwardToSandbox`) sends requests to
`http://{taskPrivateIp}:{port}/execute` (port from `SANDBOX_SERVER_PORT`, default `8080`) and
expects:

- **`POST /execute`**
  - Request: `{"files": {"relative/path/to/file": "file content", ...}, "command": "shell command string"}`
  - Behavior expected: write every file to disk under a fixed working directory (e.g. `/app`),
    creating parent directories as needed — **this overwrites whatever was baked into the image
    at build time at the same path**, which is exactly how the user's live edits take effect.
    Then execute `command` as a shell command with that directory as `cwd`, with a bounded
    timeout (60-90s is reasonable) so a runaway test run can't hang the task indefinitely.
  - Response: `{"success": bool, "stdout": string, "stderr": string, "exit_code": int}`
- **`GET /health`** — returns `200` once ready to accept traffic.

A working implementation of this exact contract now exists at
`admin-backend/src/main/resources/sandbox-runner/main.go` (a small Go HTTP server, not the
Python/FastAPI `platform-execution_service/executors/sandbox_server.py` this section originally
pointed to — that path doesn't exist in this repo). It's compiled to a binary at
`admin-backend`'s Docker build time (`admin-backend/Dockerfile`'s `go-build` stage) and baked
into every problem image by `DockerfileTemplates`, set as each image's `CMD`.

**Whatever implements this must be set as the image's `CMD` (or `ENTRYPOINT`) explicitly.** If the
main process ever exits — crashes, finishes a one-shot task, or falls back to a base image's
default — ECS marks the task `STOPPED` immediately, regardless of why. There is no "container
idles after its first job" behavior to rely on; the listener has to *be* the main process.

### Build-time requirements

- **Dependencies must be resolvable offline** at Run/Submit time. The backend's run command
  (currently `mvn -o test -Dsurefire.skipAfterFailureCount=1` for Java — see §4 for the
  multi-language gap) assumes no network access is needed. Pre-fetch everything the test command
  will need during the image build (e.g. `mvn -B dependency:go-offline`, `npm install`,
  `pip install -r requirements.txt`), so the live run never hits the network.
- The problem's own dependency manifest (`pom.xml`/`package.json`/`requirements.txt`) needs to be
  present at build time for that pre-fetch step to know what to resolve — even though the actual
  source files get overwritten at runtime by whatever the user currently has open in the editor.

---

## 3. ECR / Database Requirements

- **`ecr_image_uri`** (`problems` table, `VARCHAR(1024)`, nullable) must be a complete, pullable
  reference: `<account>.dkr.ecr.<region>.amazonaws.com/<repo>[:<tag>|@sha256:<digest>]`. Not a
  bare digest, not a repo name alone.
- **Same region as the ECS cluster** the backend is configured against (`ECS_CLUSTER_ARN`'s
  region) — required for acceptable cold-start latency, not just correctness.
- **`hidden_test_key`** (`problems` table, `VARCHAR(1024)`, nullable, added this session) — the
  exact S3 key, relative to the `gold-masters` bucket, of that problem's hidden-test zip (e.g.
  `java/ticket-booking-easy.zip`). This exists because deriving the key from
  `language + "/" + slug + ".zip"` breaks the moment the zip's filename doesn't exactly match the
  problem's slug — which was already the case for problems tested in this session. Whatever
  writes `ecr_image_uri` should write this alongside it.
- Image size isn't free even when "reasonable" (low hundreds of MB) — every problem-open pays the
  full pull cost fresh, since Fargate has no cross-task layer cache. Leaner images directly
  reduce per-session cold-start time. Secondary to correctness (§2), but worth keeping in mind.

---

## 4. Open Decisions — resolved

1. **ECR repository layout**: resolved as one shared repo with per-problem tags.
   `admin-backend`'s `DockerImageService.buildAndPush()` tags each image as
   `${ECR_REPOSITORY_URI}:${slug}` and pushes to that single configured repository — matching
   what had already been pushed manually, not the per-problem-repo layout the README used to
   describe (README has been corrected).
2. **Multi-language run commands**: resolved. `ExecutionService.LANGUAGE_COMMANDS` is a static
   `Map.of("java", "mvn -o test ...", "node", "npm test", "python", "pytest")` keyed by
   `problem.getLanguage()`, used by both `RunService` and `SubmitService` via
   `ExecutionService.resolveCommand(language)`. No DB column was needed. `DockerImageService`/
   `DockerfileTemplates` build matching images for all three languages today.

Also confirmed resolved: the reference `sandbox_server.py` this document describes is implemented
(not as Python/FastAPI, but as an equivalent Go binary,
`admin-backend/src/main/resources/sandbox-runner/main.go`, compiled at image-build time and set
as each challenge image's `CMD`) and satisfies the `/execute` + `/health` contract in §2 exactly.
