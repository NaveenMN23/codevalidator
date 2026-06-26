# Scalable Challenge Platform

A robust, multi-service platform for hosting and managing technical interview challenges. This platform enables the generation of challenge environments, automated grading, and a seamless browser-based IDE experience.

For a detailed technical breakdown, see the **[Architecture Documentation](./ARCHITECTURE.md)**.

## Key Features
*   **WebContainer IDE:** High-fidelity browser-based coding environment with Node.js support.
*   **WASM-Powered Storage:** Uses WASM SQLite (`sql.js`) for seamless local storage in the browser without native C++ bindings.
*   **Background Installation:** Dependencies install automatically in the background as soon as you enter a challenge.
*   **Modern UI:** Clean, viewport-locked IDE layout with resizable panels and terminal toggling.
*   **Automated Auto-save:** User drafts are saved to the cloud every 2 seconds and isolated per-user.

## Service Map
- **[Platform Backend](./platform-backend_service):** Java (Spring Boot) managing core logic, users, submissions, and Fargate orchestration.
- **[Platform UI](./platform-ui):** React (Vite) frontend providing the "CodeForge" IDE experience.
- **[Codegen](./platform-codegen):** Service for generating challenge assets, building problem Docker images, and pushing them to ECR.
- **Fargate Sandbox Tasks:** Short-lived AWS Fargate containers (one per user+problem session) running problem-specific Docker images from ECR with an embedded sandbox HTTP server.

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for local UI development)
- Java 21 & Python 3.11 (for core service development)

### Running with Docker
```bash
# Start the entire platform
docker compose up --build -d

# Stop the environment
docker compose down

# Rebuild only specific services after changes
docker compose up --build ui backend
```

Access the UI at: `http://localhost:5173`

---

## Execution Architecture: AWS Fargate

### Why We Moved Away from the Local Execution Service

The original `platform-execution_service` was a Python FastAPI server that managed Docker containers locally via the Docker daemon on a single EC2 host. While simple, it had two fundamental problems at scale:

1. **Fixed cost, variable demand.** The EC2 host ran 24/7 regardless of load. At 2am with zero users, you paid the same as peak.
2. **Hard capacity ceiling.** All user containers shared the same host's CPU and RAM. Scaling required manually provisioning a larger instance and redeploying.

### The New Model: One Fargate Task Per User Session

When a user opens a problem, the backend spawns a dedicated AWS Fargate task from that problem's pre-built Docker image in ECR. The task stays alive for the duration of the session and terminates after 10 minutes of inactivity.

```
User opens problem
  → Backend: look up ecr_image_uri from DB
  → Redis miss → ECS.runTask(ecrImageUri) → poll until RUNNING → capture private IP
  → Redis.set(sessionId → {taskArn, privateIP}, TTL=10min)

User hits Run
  → Redis hit → private IP
  → POST files → http://{privateIP}:8080/execute → stdout/stderr
  → Redis TTL refreshed

User hits Submit
  → Redis hit → private IP
  → S3 fetch hidden test ZIP (gold-masters bucket)
  → POST files + hidden test → http://{privateIP}:8080/execute
  → Redis TTL refreshed

10 min inactivity → Redis key expires → Fargate task self-terminates
```

Each Fargate container runs a tiny embedded FastAPI server (`sandbox_server.py`) that writes files to `/app` and runs the build command. Hidden test injection happens in the backend before the request is forwarded — the sandbox is intentionally kept dumb.

### Why Not Share One Container Per Problem?

An intuitive optimisation is to keep one warm container per problem and route all users to it. We considered this and rejected it for two reasons:

- **Resource contention.** If 20 users hit the same problem simultaneously, all their `mvn test` runs compete inside one container's CPU and memory budget. One heavy build starves everyone else.
- **Weak process isolation.** Users in the same container share the network namespace and can see each other's processes.

Per-user containers give full isolation with no contention. The cold start (30–60s Fargate task startup) is mitigated by starting the task when the user opens the problem, not when they click Run — by the time they've read the brief and written their first line, the container is ready.

### Why Not a Warm Pool?

A warm pool (pre-spawned idle containers per problem) would eliminate the cold start entirely. We deliberately deferred this. At early stage with low concurrency, the pool would mostly sit idle and cost money for nothing. The upgrade path is clear: replace `spawnAndRegister()` in `ExecutionService` with a pool-claim call, and the rest of the architecture is unchanged.

### Cost Comparison

| | Previous (EC2 + Docker daemon) | Fargate |
|---|---|---|
| Baseline (0 users) | ~$60–120/month fixed | ~$13/month (Redis only) |
| 10 sessions/day | ~$73/month | ~$22/month |
| 100 sessions/day | ~$73/month | ~$46/month |
| 500 sessions/day | ~$120/month+ (needs resize) | ~$90/month (auto-scales) |

**Break-even is ~250 sessions/day.** Below that, Fargate is cheaper. Above that, costs are comparable but Fargate scales automatically with no operational intervention.

ECR adds ~$1/month for image storage (shared base layers mean 50 problems ≠ 50× the storage). A VPC endpoint for ECR (~$7/month) eliminates data-transfer charges for image pulls within the region.

### What platform-codegen Owns

After publishing a problem, platform-codegen is responsible for:
1. Building the problem's Docker image (base executor image + problem-specific dependencies pre-compiled)
2. Pushing the image to ECR
3. Writing the resulting ECR URI back to the problem's `ecr_image_uri` column in the DB

The backend returns `422 Unprocessable Entity` if `ecr_image_uri` is null, which surfaces clearly during development when an image hasn't been pushed yet.

### Required AWS Infrastructure

The following must exist before Fargate execution works (AWS console or IaC, out of code scope):

| Resource | Purpose |
|---|---|
| ECS Cluster | Hosts Fargate tasks |
| Private subnets (×2 min) | Task network placement |
| Security group for tasks | Allow inbound :8080 from backend SG only |
| ECR repository per problem | Stores problem Docker images |
| IAM task role | Allows tasks to run; no S3/ECS access needed |
| IAM execution role | Allows ECS to pull from ECR and push logs |

Set `ECS_CLUSTER_ARN`, `ECS_SUBNET_IDS`, and `ECS_SECURITY_GROUP_ID` as environment variables on the backend service.

---

## Engineering Standards

### 1. User Data Isolation
All persistent data (drafts, submissions) MUST be keyed by `userId`. Cross-user data leakage is a critical security failure.

### 2. Browser Compatibility
All challenge code must be browser-compatible. Native C++ modules (like `better-sqlite3`) are prohibited; use WASM alternatives (like `sql.js`) for local storage.

### 3. Asynchronous Grading
Grading must never block the main request thread. Use the RabbitMQ-based worker flow for all code execution and validation.

### 4. Resilience
External service calls (DB, Redis, RabbitMQ) MUST implement retry patterns (Spring Retry or Tenacity) to handle transient infrastructure blips.
