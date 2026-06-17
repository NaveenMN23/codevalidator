# Platform Workers

Python-based background workers responsible for isolated code execution and grading.

## Tech Stack
- **Engine:** Docker (Ephemeral Sandboxing)
- **Language:** Python 3.11
- **Messaging:** RabbitMQ (Pika)
- **Logging:** Loguru

## Key Features
- **Isolated Sandboxing:** Executes candidate code in network-disabled, resource-constrained Docker containers.
- **AI Evaluation Engine:** For premium submissions, performs deep analysis using LLMs (Claude 3 Haiku) to provide feedback on correctness, efficiency, and interviewer follow-ups.
- **Optimization:** Leverages **Anthropic Prompt Caching** and local **Semantic Caching** (Redis) to minimize AI unit costs and latency.
- **Bi-Directional Messaging:** Consumes grading jobs and publishes structured results (stdout, stderr, exit codes, and AI feedback).

## Standard Grading Flow
1.  **Consume:** Pick up `GradingJob` from RabbitMQ.
2.  **Stage:** Create a unique temporary directory and write the candidate's JSON file map to disk.
3.  **Execute (Docker):** Run language-specific test commands (e.g., `npm test`) inside an ephemeral, network-isolated Docker container.
4.  **Analyze (AI):** If `isPremium` is true and the run was successful:
    - Fetch the **Blueprint** context from Redis.
    - Check the **Semantic Cache** for identical logic hashes.
    - Call the **LLM Evaluator** (with Prompt Caching) for deep analysis.
5.  **Publish:** Post an enriched `GradingResult` back to the results queue.
6.  **Cleanup:** Securely remove the temporary directory and destroy the container.

## Configuration
Worker limits and AI settings are controlled via environment variables:
- `DOCKER_MEM_LIMIT`: Default `512m`
- `DOCKER_TIMEOUT_SECONDS`: Default `30`
- `ANTHROPIC_API_KEY`: Required for AI evaluation.
- `REDIS_HOST` / `REDIS_PORT`: For blueprint caching and semantic caching.

## Run Locally
```bash
pip install -r requirements.txt
python3 src/main.py
```
