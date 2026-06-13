# Codex / GitHub Copilot Development Standards

This file provides instructions for Codex/Copilot-based AI tools working on the Scalable Challenge Platform.

## Core Mandates

1.  **Architecture:** Decoupled microservices (`platform-backend` in Java, `platform-codegen` in Python).
2.  **Messaging:** Async communication via RabbitMQ is required for heavy tasks.
3.  **Resilience Patterns:**
    *   **Java:** `@Retryable` (spring-retry).
    *   **Python:** `@retry` (tenacity).
    *   **Node.js:** `retry` (async-retry).
4.  **Testing:** Python tests belong in `platform-codegen/tests/`.
5.  **Docker:** Use `docker-compose.yml` for local development and verification.

## Tech Stack
- Java 21 / Spring Boot 3
- Python 3.11 / FastAPI
- Node.js / Fastify
- React / Vite
- PostgreSQL, Redis, RabbitMQ, SQLite
