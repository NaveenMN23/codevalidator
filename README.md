# Scalable Challenge Platform

A robust, multi-service platform for hosting and managing technical interview challenges. This platform enables AI-driven challenge generation, tiered difficulty levels, automated grading, and a seamless browser-based IDE experience.

For a detailed technical breakdown, see the **[Architecture Documentation](./ARCHITECTURE.md)**.

## Key Features

- **Tiered Challenges**: Three structurally distinct codebases per challenge — Easy (SDE1/SDE2), Medium (SDE2/SDE3), Advanced (SDE3/Staff/Principal)
- **AI-Driven Generation**: Two-phase CoT pipeline generates gold master implementations + blueprints using GPT-4o
- **Hidden Tests**: Server-side hidden tests stored in MinIO `gold-masters/` bucket; fetched on-demand by workers — volume-independent
- **Blueprint-Based Evaluation**: Each scenario has a blueprint (task description, gold master reference, seniority signals, scoring rubric) used by GPT-4o mini for AI feedback
- **Interview Sessions**: B2B mode links candidates + interviewers, produces structured hiring assessments with panel questions
- **WebContainer IDE**: High-fidelity browser-based coding environment with Node.js support
- **Asynchronous Grading**: Submissions flow: Backend → RabbitMQ → Workers → Docker sandbox → LLM evaluator → Result

## Service Map

| Service | Language | Port | Responsibility |
|---|---|---|---|
| **[platform-backend](./platform-backend)** | Java 21 / Spring Boot 3 | 8080 | Business logic, submissions, interview sessions, blueprint storage |
| **[platform-ui](./platform-ui)** | React / Vite | 5173 | WebContainers IDE, dashboard, challenge selection |
| **[platform-workers](./platform-workers)** | Python | — | Docker code execution, AI evaluation (GPT-4o mini) |
| **[platform-codegen](./platform-codegen)** | Python / FastAPI | 8000 | Gold master generation (GPT-4o), blueprint creation, MinIO upload |

## Infrastructure

| Service | Port | Purpose |
|---|---|---|
| PostgreSQL 16 | 5432 | Users, challenges, submissions, blueprints, interview sessions |
| Redis 7 | 6379 | Blueprint cache (24hr TTL), semantic eval cache (24hr TTL) |
| RabbitMQ 3 | 5672 | Grading queue, results queue |
| MinIO | 9000 | `challenges/` (public — student scaffolds), `gold-masters/` (private — reference solutions + hidden tests) |

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
docker compose up --build codegen workers
```

Access the UI at: `http://localhost:5173`  
Admin Swagger UI: `http://localhost:8080/swagger-ui.html`  
MinIO Console: `http://localhost:9001` (admin / password)

## Challenge Creation Flow

1. Admin calls `POST http://localhost:8000/admin/generate-golden-repo` with a problem description
2. **Phase 1** (GPT-4o): designs three separate codebase architectures (easy/medium/advanced)
3. **Phase 2** (GPT-4o × 3): implements each tier — complete gold master + hidden test per tier
4. Each tier is uploaded to MinIO:
   - `challenges/{lang}/{name}-{tier}.zip` → student-facing scaffold (public)
   - `gold-masters/{lang}/{name}-{tier}.zip` → gold master + hidden tests (private)
5. Blueprints are generated per scenario and stored in Postgres + Redis

## Engineering Standards

### 1. User Data Isolation
All persistent data (drafts, submissions) MUST be keyed by `userId`. Cross-user data leakage is a critical security failure.

### 2. Gold Master Security
`goldMasterSource` is stored in blueprint JSONB in Postgres. It must **never** be returned in student-facing API responses. Only workers and admin endpoints may access it.

### 3. Asynchronous Grading
Grading must never block the main request thread. Use the RabbitMQ-based worker flow for all code execution and validation.

### 4. Resilience
External service calls (DB, Redis, RabbitMQ, MinIO) MUST implement retry patterns:
- **Java**: `spring-retry` (3 attempts, exponential backoff, initial 1s, multiplier 2.0)
- **Python**: `tenacity` (`stop_after_attempt(3)`, `wait_exponential`)

### 5. Volume Independence
Workers fetch hidden tests from MinIO on-demand at grading time (in-memory cached per process). The grading pipeline never depends on the local filesystem volume for correctness — it is always restorable from MinIO.
