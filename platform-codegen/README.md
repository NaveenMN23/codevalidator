# Platform Codegen Service

AI-driven service responsible for generating tiered coding challenge assets — gold masters, student scaffolds, hidden tests, and blueprints — using a three-phase Chain-of-Thought pipeline.

## Tech Stack

| Component | Technology |
|---|---|
| Framework | FastAPI (Python 3.11) |
| LLM | OpenAI GPT-4o (automatic prefix caching for cost efficiency) |
| Cache | Redis |
| Storage | MinIO / S3 (boto3) |
| Queue | RabbitMQ (pika) — blueprint persistence |
| Resilience | Tenacity (retry with exponential backoff) |

---

## Generation Pipeline

```
POST /admin/generate-golden-repo
  { prompt, languages?, tiers?, scenarios_per_tier? }
  │
  ├── Phase 1 — Design (runs ONCE, language-agnostic)
  │     design_challenge.mdx → DesignOutput
  │     • One codebase design per requested tier
  │     • Exactly N scenarios per tier
  │     • Scenario types: implement (stub) or debug (broken code)
  │
  └── Phase 2 — Per language (loops over each requested language)
        │
        ├── Phase 2a — Skeleton (per tier)
        │     implement_skeleton_{lang}.mdx → SkeletonOutput
        │     • Full codebase with stubs for implement scenarios
        │     • Intentionally broken code for debug scenarios
        │     • Per-scenario README-{tag}.md with tier-specific instructions
        │
        ├── Phase 2b — Function Deltas (per scenario)
        │     implement_function_{lang}.mdx  → FunctionDeltaOutput  (implement)
        │     debug_function_{lang}.mdx      → FunctionDeltaOutput  (debug)
        │     • Correct function body (injected into gold master)
        │     • Hidden test file (must fail against bug, pass against fix)
        │
        ├── Assembly
        │     gold master  = skeleton + all N deltas injected back
        │     student scaffold = skeleton as-is + scenario README
        │
        ├── Upload
        │     MinIO gold-masters/{lang}/{name}-{tier}.zip  (private)
        │     MinIO challenges/{lang}/{name}-{scenario}.zip (public)
        │     Local /generated/{name}/{lang}/...            (dev export)
        │
        └── Phase 3 — Blueprints (per scenario)
              generate_blueprint.mdx → blueprint JSON
              • Written directly to Redis  blueprint:{problemId}  (AI eval reads here)
              • Published to RabbitMQ  blueprint-queue  (backend persists to Postgres)
```

---

## Tier Architecture

| Tier | Target | Architecture | Files | Scenario Types |
|---|---|---|---|---|
| **Easy** | SDE1/SDE2 | Layered MVC (`controllers/`, `services/`, `repositories/`) | 5–7 | All `implement` |
| **Medium** | SDE2/SDE3 | Feature-based packaging (`booking/`, `common/`) | 9–12 | Mostly `implement`, 1 `debug` |
| **Hard** | SDE3/Staff | Clean/Hexagonal Architecture (`domain/`, `application/`, `infrastructure/`) | 14–17 | 1 `implement`, 2 `debug` |

### Scenario Types

- **`implement`** — Target function is a stub with `throw new Error("not implemented: {tag}")`. Student fills in the body.
- **`debug`** — Target function has intentionally broken logic (wrong state, missing idempotency, race condition). Marked with `# DEBUG_SCENARIO: {tag}` comment. Student finds and fixes the bug.

---

## Blueprint Dispatch

Blueprints are persisted via two independent paths to ensure AI evaluation always works even if the backend is temporarily down:

1. **Redis** (direct write from codegen) — `blueprint:{problemId}` key. This is what the grading workers read for AI evaluation. Written first, unconditionally.
2. **RabbitMQ** (`blueprint-queue`) — durable message. The backend consumes this and persists to Postgres. If the backend is down, messages queue up and are consumed on recovery.

---

## Request Model

```json
{
  "prompt": "Build a vending machine challenge...",
  "languages": ["node"],           // "node" | "java" | "python" — default: ["node"]
  "tiers": ["easy", "medium", "hard"],   // default: all three
  "scenarios_per_tier": 3,         // 1–5, default: 3
  "use_local_few_shots": false
}
```

> **Note:** The legacy singular `"language": "java"` field is also accepted and automatically converted to `"languages": ["java"]`.

---

## Output Structure

```
generated/
  {challenge-name}/
    {language}/
      scaffold/
        {scenario-tag}/          ← extracted student ZIP (human-readable)
      gold-master/
        {tier}/                  ← extracted gold master source

dist/
  challenges/{language}/        ← scaffold ZIPs (mirrors MinIO)
  gold-masters/{language}/      ← gold master ZIPs (mirrors MinIO)
```

MinIO buckets:
- `challenges/{lang}/{name}-{scenario}.zip` — public, served to students
- `gold-masters/{lang}/{name}-{tier}.zip` — private, used by grading workers

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required |
| `OPENAI_MODEL` | `gpt-4o` | Generation model |
| `OPENAI_MAX_TOKENS_IMPL` | `16384` | Max tokens for Phase 2a (full skeleton) |
| `OPENAI_MAX_TOKENS_TEST` | `8192` | Max tokens for Phase 2b (tests) |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `AWS_ACCESS_KEY_ID` | — | AWS credentials (boto3 default chain) |
| `AWS_SECRET_ACCESS_KEY` | — | AWS credentials (boto3 default chain) |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_S3_CHALLENGES_BUCKET` | `challenges` | S3 bucket for scaffold ZIPs |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ host |
| `RABBITMQ_PORT` | `5672` | RabbitMQ port |
| `RABBITMQ_USER` | `admin` | RabbitMQ username |
| `RABBITMQ_PASSWORD` | `password` | RabbitMQ password |
| `BLUEPRINT_QUEUE` | `blueprint-queue` | Queue for blueprint persistence |
| `BACKEND_URL` | `http://platform-backend:8080` | Backend service URL |
| `LOCAL_EXPORT_PATH` | `` | Dev-only local export path (e.g. `/generated`) |
| `ENABLE_BLUEPRINT_GENERATION` | `true` | Feature flag for blueprint generation |
| `ENABLE_LLM` | `true` | Feature flag for all LLM calls |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/generate-golden-repo` | Full three-phase generation pipeline |
| `GET` | `/health` | Health check |

---

## Development

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Docker
```bash
docker compose up --build codegen
```

### Tests
```bash
PYTHONPATH=. pytest tests/
```
