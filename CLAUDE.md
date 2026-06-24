# Claude AI Development Standards

This file provides instructions for Claude-based AI agents working on the Scalable Challenge Platform. Follow these rules to maintain architectural integrity and resilience.

## Core Architectural Mandates

1.  **Service Decoupling:**
    *   `platform-backend` (Java) handles business logic and orchestration.
    *   `platform-codegen` (Python) handles asset generation and caching.
    *   Communication between them MUST remain asynchronous via **RabbitMQ**.
    *   **Exception — `platform-eval`:** The AI interview evaluation service uses **synchronous REST** (`/eval/submit`, `/eval/answer`, `/eval/session/{id}`). This is a deliberate, documented exception: an interactive human-in-the-loop interviewer has the opposite shape from fire-and-forget grading and cannot use an async queue.

2.  **Resilience (Transient Error Handling):**
    *   **Java:** Use `spring-retry` for DB/RabbitMQ. Standard: 3 attempts, exponential backoff (initial: 1s, multiplier: 2.0).
    *   **Python:** Use `tenacity` for Redis/Network operations. Standard: `stop_after_attempt(3)`, `wait_exponential`.
    *   **Node.js:** Use `async-retry` for SQLite transactions (`SQLITE_BUSY`).

3.  **Project Structure:**
    *   Keep the root folder clean. Global configs only.
    *   Python Tests MUST live in `platform-codegen/tests/` and use relative imports.
    *   Add new challenges under `challenges/` following the existing `book-my-show` structure.

4.  **Docker-First Workflow:**
    *   Always verify changes via `docker compose up --build [service]`.
    *   Ensure `platform-codegen/Dockerfile` copies all necessary modules (api, infrastructure, services).

## Workflow Mandates

*   **PR Template:** Use the template in `.github/pull_request_template.md` for all modifications.
*   **Documentation:** Updates MUST be reflected in `ARCHITECTURE.md` and relevant service `README.md` files.
*   **Validation:** Use `mvnw`, `npm`, or `pytest` to verify changes before finalizing.

## Tech Stack
*   **Java:** Spring Boot 3, Java 21, Flyway.
*   **Python:** FastAPI, Python 3.11, Redis.
*   **Node.js:** Fastify, Kysely (SQLite).
*   **Frontend:** React, Vite, WebContainers.
