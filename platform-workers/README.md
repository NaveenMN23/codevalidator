# Platform Workers

Python-based background workers responsible for isolated code execution and grading.

## Tech Stack
- **Engine:** Docker (Ephemeral Sandboxing)
- **Language:** Python 3.11
- **Messaging:** RabbitMQ (Pika)
- **Logging:** Loguru

## Key Features
- **Isolated Sandboxing:** Executes candidate code in network-disabled, resource-constrained Docker containers.
- **Bi-Directional Messaging:** Consumes grading jobs and publishes structured results (stdout, stderr, exit codes).
- **Multi-Language Support:** Configurable executors for Node.js, Python, Java, and C++.
- **Robustness:** Implements `tenacity` retries for broker connections.

## Standard Grading Flow
1.  **Consume:** Pick up `GradingJob` from RabbitMQ.
2.  **Stage:** Create a unique temporary directory and write the candidate's JSON file map to disk.
3.  **Execute:** Run language-specific test commands (e.g., `npm test`) inside an ephemeral Docker container.
4.  **Capture:** Extract status codes, standard output, and error logs.
5.  **Publish:** Post a `GradingResult` back to the results queue.
6.  **Cleanup:** Securely remove the temporary directory and destroy the container.

## Configuration
Worker limits are controlled via environment variables (see `docker-compose.yml`):
- `DOCKER_MEM_LIMIT`: Default `512m`
- `DOCKER_TIMEOUT_SECONDS`: Default `30`
- `DOCKER_PIDS_LIMIT`: Default `50`

## Run Locally
```bash
pip install -r requirements.txt
python3 src/main.py
```
