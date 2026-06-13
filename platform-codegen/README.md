# Python Codegen Service

The generator service responsible for creating challenge repositories and assets.

## Tech Stack
- **Framework:** FastAPI
- **Language:** Python 3.11
- **Cache:** Redis
- **Storage:** AWS S3 / MinIO (boto3)
- **Resilience:** Tenacity (Retry logic)

## Key Features
- **Dynamic Generation:** Uses templates and stripping logic to create "starter" and "solution" repositories from a "gold master."
- **Caching:** Aggressively caches generation results in Redis to minimize compute time.
- **Robustness:** Handles transient Redis connection issues with exponential backoff retries.

## Development

### Setup
```bash
pip install -r requirements.txt
```

### Run
```bash
uvicorn main:app --reload --port 8000
```

### Testing
Run tests using:
```bash
PYTHONPATH=. python3 tests/test_engine.py
```
