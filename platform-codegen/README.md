# Platform Codegen Service

AI-driven service responsible for generating tiered coding challenge assets — gold masters, student scaffolds, blueprints, and hidden tests.

## Tech Stack
- **Framework:** FastAPI
- **Language:** Python 3.11
- **LLM:** OpenAI GPT-4o (generation) — automatic prefix caching for cost efficiency
- **Cache:** Redis
- **Storage:** MinIO / S3 (boto3)
- **Resilience:** Tenacity (retry with exponential backoff)

## Key Features

- **Two-Phase CoT Generation:**
  - Phase 1 (`design_challenge.mdx`): GPT-4o designs three structurally different codebases — one per tier
  - Phase 2 (`implement_gold_master_{language}.mdx` × 3): GPT-4o implements each tier separately — full gold master + one hidden test per tier
- **Tiered Difficulty:** Each challenge has three distinct implementations:
  - **Easy** (2-3 files, flat architecture) → SDE1/SDE2
  - **Medium** (5-7 files, layered service architecture) → SDE2/SDE3
  - **Advanced** (8-12 files, enterprise patterns) → SDE3/Staff/Principal
- **Durable Storage:**
  - Student scaffolds → MinIO `challenges/` (public)
  - Gold masters + hidden tests → MinIO `gold-masters/` (private — admin only)
  - Blueprints with `goldMasterSource` → Postgres + Redis
- **Input Sanitization:** Injection pattern detection, path traversal guard, per-file size limits
- **Output Validation:** Pydantic models validate LLM output schema; correction prompts on failure (max 2 retries)

## Generation Flow

```
POST /admin/generate-golden-repo { prompt, language }
  │
  ├── Phase 1: GPT-4o → DesignOutput (3 tier designs)
  │
  ├── Phase 2 × 3: GPT-4o → SingleTierOutput per tier
  │     Each tier: files (N files) + test_hidden (1 test file)
  │
  ├── For each tier:
  │     ├── Write to /challenges/{name}/apps/gold-master-{tier}-{language}/
  │     ├── engine.generate() → student scaffold ZIP (strips @strip-target blocks)
  │     ├── Upload scaffold → MinIO challenges/{lang}/{name}-{tier}.zip (public)
  │     └── Upload gold master → MinIO gold-masters/{lang}/{name}-{tier}.zip (private)
  │
  └── Blueprint generation per scenario:
        GPT-4o → blueprint JSON (task, repo, evaluation, rubric, followUpContext)
        Post-process: embed goldMasterSource (relevant files only)
        POST /api/admin/blueprints → Postgres + Redis
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required |
| `OPENAI_MODEL` | `gpt-4o` | Generation model |
| `OPENAI_MAX_TOKENS_IMPL` | `16384` | Max tokens for Phase 2 (full file tree) |
| `MINIO_ENDPOINT` | `http://localhost:9000` | |
| `MINIO_BUCKET` | `challenges` | Public scaffold bucket |
| `REDIS_HOST` | `localhost` | |
| `BACKEND_URL` | `http://backend:8080` | Blueprint dispatch target |

## Development

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Testing
```bash
PYTHONPATH=. python3 tests/test_engine.py
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/generate-golden-repo` | Generate tiered gold masters + blueprints |
| `POST` | `/generate` | Generate scaffold ZIP from existing gold master |
| `GET` | `/health` | Health check |
