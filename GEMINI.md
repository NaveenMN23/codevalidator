# Gemini CLI Development Standards

This file provides foundational mandates for AI agents (specifically Gemini CLI) working on the Scalable Challenge Platform. Adhere to these rules to maintain architectural integrity and resilience.

## Core Architectural Mandates

1.  **Service Decoupling:**
    *   `platform-backend` (Java) handles business logic and orchestration.
    *   `platform-codegen` (Python) handles asset generation and caching.
    *   Communication between them MUST remain asynchronous via **RabbitMQ** for processing-intensive tasks.

2.  **Resilience (Transient Error Handling):**
    *   **Java:** Use `spring-retry` for database and RabbitMQ operations. Standard: 3 attempts, exponential backoff (initial: 1s, multiplier: 2.0).
    *   **Python:** Use `tenacity` decorators for Redis and network-bound operations. Standard: `stop_after_attempt(3)`, `wait_exponential`.
    *   **Node.js:** Use `async-retry` for SQLite transactions to handle `SQLITE_BUSY` errors.

3.  **Project Structure:**
    *   **Root Folder:** Keep it clean. Only global config (`docker-compose.yml`, `.github/`, `README.md`, `ARCHITECTURE.md`, `GEMINI.md`).
    *   **Python Tests:** MUST live in `platform-codegen/tests/` and use relative imports (run with `PYTHONPATH=.`).
    *   **New Challenges:** Should be added under `challenges/` following the existing `book-my-show` structure.

4.  **Docker-First Workflow:**
    *   Always verify changes via `docker compose up --build [service]`.
    *   When updating `platform-codegen`, ensure the `Dockerfile` copies all necessary modules (api, infrastructure, services).

## Workflow Mandates

*   **PR Template:** Every code modification MUST be accompanied by a PR summary using the template in `.github/pull_request_template.md`.
*   **Documentation:** Updates to core logic MUST be reflected in `ARCHITECTURE.md` and relevant service `README.md` files.
*   **Validation:** Never assume success. After making a change, attempt to verify it using the project's build tools (`mvnw`, `npm`, `pytest/python3`).

## Tech Stack Defaults

*   **Java:** Spring Boot 3, Java 21, Flyway, Spring Data JPA.
*   **Python:** FastAPI, Python 3.11, Redis, Boto3 (S3).
*   **Node.js:** Fastify, Kysely (SQLite), Zod.
*   **Frontend:** React, Vite, WebContainers.
