# Platform Workers

Python-based background workers responsible for isolated code execution and AI-powered evaluation.

## Tech Stack
- **Engine:** Docker SDK (ephemeral sandboxing)
- **Language:** Python 3.11
- **Messaging:** RabbitMQ (Pika)
- **LLM:** OpenAI GPT-4o mini (AI evaluation) — automatic prefix caching
- **Storage:** MinIO / S3 (boto3) — on-demand hidden test fetching
- **Logging:** Loguru

## Key Features

- **Volume-Independent Grading:** Hidden tests are fetched on-demand from MinIO `gold-masters/` bucket (in-memory cached per process). The grading pipeline never breaks silently if the Docker volume is wiped.
- **Tiered Challenge Support:** Automatically extracts the tier from the challenge ID (`book-my-show-easy` → tier=`easy`) to fetch the correct hidden tests and gold master.
- **AI Evaluation:** GPT-4o mini evaluates correctness, efficiency, and provides interviewer follow-up. Receives test failure details, gold master reference, seniority signals, and a scoring rubric from the blueprint.
- **B2B Hiring Mode:** When `userType=B2B`, produces a structured hiring assessment with recommendation, confidence, strengths, concerns, and panel questions.
- **Prompt Caching:** Blueprint system prompt (with goldMasterSource) is static per challenge scenario — OpenAI auto-caches matching prefixes > 1024 tokens (~50% discount on repeated evaluations).
- **Semantic Cache:** Redis caches AI feedback by SHA256 hash of submission (24hr TTL) — identical code submissions skip the LLM entirely.
- **Isolated Sandboxes:** Internal Docker network (loopback works, no internet), resource limits per language.

## Grading Flow

```
RabbitMQ grading-queue → GradingConsumer
  │
  ├── Extract (base_challenge_id, tier) from challengeId
  │     "book-my-show-easy" → ("book-my-show", "easy")
  │
  ├── Fetch blueprint: Redis → Postgres fallback (re-warms Redis on miss)
  │
  ├── Fetch hidden tests: GoldMasterStorage.get_hidden_tests(name, tier, lang)
  │     Fetches gold-masters/{lang}/{name}-{tier}.zip from MinIO
  │     Extracts test-hidden/ entries → caches in process memory
  │
  ├── Stage submission files to /tmp/grading_stages/{uuid}/
  ├── Inject hidden tests into staging dir
  │
  ├── DockerExecutor.execute() → sandboxed container
  │     - platform/node-executor (baked node_modules)
  │     - platform/python-executor (baked venv)
  │     - openjdk:17-jdk-slim (Java + Maven cache)
  │     - Timeouts: 45s Java / 30s others
  │
  ├── Extract first test failure for focused feedback UX
  ├── Publish initial result → results-queue
  │
  └── If isPremium + success: AI evaluation
        LLMEvaluator.evaluate(blueprint, submission, test_results, remaining_time, user_type)
        → GPT-4o mini with goldMasterSource + rubric + seniority signals
        → {correctness, efficiency, followUp, summary, [hiring if B2B]}
        → Semantic cache → Publish enriched result
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required for AI evaluation |
| `OPENAI_MODEL` | `gpt-4o-mini` | Evaluation model |
| `ENABLE_AI_EVALUATION` | `false` | Global AI toggle |
| `MINIO_ENDPOINT` | `http://localhost:9000` | For hidden test fetching |
| `MINIO_ACCESS_KEY` | `admin` | |
| `MINIO_SECRET_KEY` | `password` | |
| `BACKEND_URL` | `http://backend:8080` | For blueprint Postgres fallback |
| `REDIS_HOST` / `REDIS_PORT` | `localhost:6379` | Blueprint + semantic cache |
| `RABBITMQ_HOST` | `localhost` | |
| `DOCKER_MEM_LIMIT` | `512m` | |
| `DOCKER_TIMEOUT_SECONDS` | `30` | (Java uses 45s) |

## Run Locally

```bash
pip install -r requirements.txt
python3 src/main.py
```

Scale workers: `docker compose up --scale workers=4`
