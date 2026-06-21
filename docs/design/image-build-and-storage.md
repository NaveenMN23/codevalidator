# Design Note: Per-Challenge Image Build — Current State & Future Options

**Status:** Describes what's actually built and validated today, plus options for evolving it.
Not a decision log for unresolved items — those are called out explicitly in §3.

---

## 1. Current State (built, validated)

### 1.1 When the build happens: publish time, not click time

Triggered from `platform-codegen/services/orchestrator.py`'s `orchestrate_generation()`,
**synchronously, within the same `/generate` call that publishes a challenge** — after the
student-facing zip is generated and uploaded to S3/MinIO, `_trigger_image_build()` calls
`POST /build-challenge-image` on the Execution Service, before `/generate` returns to the caller.

By the time a challenge is "published," its Docker image already exists, fully built. No
dependency installation, no network access, no S3 access happens at Run/Submit click time —
that cost is paid once, at publish time, deliberately (see
`docs/design/repo-execution-architecture.md` §4).

### 1.2 What actually builds it: `ChallengeImageBuilder`

`platform-execution_service/src/challenge_image_builder.py`:

1. Reads the challenge's `pom.xml` from the local `challenges/{name}/apps/gold-master-{lang}/`
   mount (today; see §3 for the S3 alternative).
2. Builds `FROM platform/{lang}-executor:latest` (the shared base image, which already has the
   build-lifecycle plugins — compiler, resources, surefire — cached from its own one-time `mvn
   test` placeholder build), `COPY pom.xml .`, `RUN mvn -B dependency:go-offline`.
3. Tags the result `platform/{lang}-executor-{challengeId}:latest` and leaves it in the local
   Docker daemon's image store.

Building *on top of* the base image (rather than from scratch) means a per-challenge build only
resolves that challenge's specific extra dependencies — the expensive part (build-plugin
resolution) is shared, paid once for the whole platform, not once per challenge.

### 1.3 Where the dependencies physically live

Baked into the image's filesystem layers — specifically Maven's `/root/.m2/repository` inside
the image, written when `dependency:go-offline` runs during `docker build`. This is **not** a
separate cache/database — it's part of the image itself. Measured directly:
`platform/java-executor-calculator:latest` came out to **~1.04GB** (base Spring Boot image +
that challenge's dependencies).

### 1.4 Persistence characteristics

- **Durable across container/daemon restarts** — once built, image layers sit on the Docker
  daemon's local disk; a container created from the image gets its own thin writable layer on
  top, but the read-only base layers (including the baked `.m2` cache) are shared across every
  container created from that image, not duplicated per-container.
- **Scoped to one host's disk** — there is currently exactly one Execution Service node, so this
  is sufficient. If a second node ever existed, an image built on node A simply would not exist
  on node B (see §2.1).
- **Cheaply regenerable, not a backup target** — the actual durable source of truth is the gold
  master source (git-tracked `challenges/` directory; the `gold-masters` S3 bucket for hidden
  tests). The image is a derived artifact, rebuildable from that source in ~30-50s (measured).
  Losing a node's local image store is an inconvenience (rebuild), not data loss.

### 1.5 How Run/Submit resolve the image

`SessionContainerManager._resolve_image()` (`platform-execution_service/src/session_container_manager.py`):
checks whether `platform/{lang}-executor-{challengeId}:latest` exists in the local image store.
If yes, use it. If no — **hard fail** (`ValueError`, surfaced as HTTP 400), no fallback to a
generic image. A challenge must be published (and its build must have succeeded) before it can
be Run or Submitted.

### 1.6 Multiple frameworks/dependency sets — handled by construction

Each challenge gets its own distinct image tag, built from *that challenge's own* `pom.xml`.
There is no shared "one big install" attempting to accommodate every framework combination —
Challenge A (e.g. Spring Data JPA + Redis) and Challenge B (e.g. Spring Kafka + WebFlux) get
fully independent images with independent dependency sets. They share only the common base
layer (generic Spring Boot starters already in `platform/java-executor:latest`); the
challenge-specific deltas are isolated per image, never mixed.

### 1.7 Re-publishing a challenge

Re-running `/generate` for an already-published challenge re-triggers the image build, which
overwrites the same `:latest` tag for that challenge — i.e., republishing automatically refreshes
the image. There is currently no versioning beyond `:latest` (see §3).

---

## 2. Future Options

### 2.1 Multi-node distribution via a container registry (e.g. ECR)

The moment there's more than one Execution Service node, "built on this host's disk" stops being
sufficient — each node needs the image, and they don't share a local Docker daemon.

- **What changes:** `ChallengeImageBuilder` would push the built image to a shared registry
  (e.g. `<account>.dkr.ecr.<region>.amazonaws.com/platform/java-executor:{challengeId}` — ECR's
  idiomatic pattern is one repository with many tags, not one repository per challenge, since ECR
  doesn't auto-create repos on push). Each node's `_resolve_image()` would need to pull on first
  use if not already cached locally.
- **What doesn't change:** none of `SessionContainerManager`'s create/reuse/reap logic, none of
  the backend's virtual-thread/Bulkhead code — `containers.run(image, ...)` behaves identically
  regardless of where the image came from.
- **Auth, mostly an ops concern, not a code concern:** if the host's Docker daemon is configured
  with `amazon-ecr-credential-helper` (typical for EC2/ECS-on-EC2 with the right IAM role), pull
  and push auth happen transparently at the daemon level — `docker-py` calls just go through the
  already-authenticated daemon.
- **Reintroduces a cold-pull cost** on whichever node serves the *first* request for a given
  challenge after that node didn't itself build the image — the same node-level pre-warming
  concern flagged in `repo-execution-architecture.md` §4.
- **Not needed today** — there is one node. Build only when a second node is real, per the
  "Resolution" section of the architecture decision log (`okay-so-you-have-wiggly-flurry.md`).

### 2.2 Extending to Node/Python

`platform-execution_service/executors/{node,python}/` already exist (Dockerfiles + base
manifests, moved but unused since `SUPPORTED_LANGUAGES = {"java"}`). Extending
`ChallengeImageBuilder`/`SessionContainerManager` to a new language means:
- Adding the language to `SUPPORTED_LANGUAGES` and `BASE_IMAGE_FOR_LANGUAGE`.
- A language-appropriate per-challenge Dockerfile template (e.g. `npm install` instead of
  `mvn dependency:go-offline`, layered on `platform/node-executor:latest`).
- No changes to the registry/persistence model — same shape, different base image and dependency
  manifest file.

### 2.3 Disk growth as the challenge catalog grows

Per-challenge images are sizable (~1GB observed for one Java challenge). As more challenges get
published, local disk usage on the Execution Service host grows roughly linearly with the catalog
size (mitigated partially by shared base layers, not eliminated by them). Options if/when this
becomes a real constraint:
- Periodic garbage collection of images for challenges that haven't been Run/Submitted in N days
  (rebuildable on demand from the gold master source if needed again — see §1.4).
- Moving to a registry (§2.1) shifts the "is it present" cost from every node's local disk to
  pull-on-demand, trading disk usage for pull latency on cold challenges.
- Not a problem yet at the current catalog size (one published challenge).

### 2.4 Image versioning beyond `:latest`

Currently re-publishing overwrites `:latest` in place — there's no way to reference "the image as
it was for submission X, made under challenge version Y." If reproducibility of past
submissions/runs against the exact dependency set they ran under ever matters (e.g. for grading
audits), tagging by a content hash of the challenge's `pom.xml` (in addition to `:latest`) would
let old images stick around addressably rather than being overwritten. Not built; flagged as an
option only.

---

## 3. Open Items Explicitly Not Decided

1. **Where `ChallengeImageBuilder` reads the dependency manifest from** — today, the local
   `challenges/` mount (shared between `codegen` and `execution-service` via Docker volume,
   single-host). If hosts ever split apart without a shared volume, this would need to become an
   S3 fetch instead — not yet needed, not yet built.
2. **Registry push/pull (§2.1)** — explicitly deferred until there's a second Execution Service
   node.
3. **Image garbage collection (§2.3)** and **versioning beyond `:latest` (§2.4)** — not needed at
   current catalog size; revisit if/when they become real constraints.
