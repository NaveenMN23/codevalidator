# Scalable Challenge Platform

A robust, multi-service platform for hosting and managing technical interview challenges. This platform enables the generation of challenge environments, automated grading, and a seamless browser-based IDE experience.

For a detailed technical breakdown, see the **[Architecture Documentation](./ARCHITECTURE.md)**.

## Architecture Overview

The system is built as a set of decoupled microservices:

*   **[Platform Backend](./platform-backend):** Java (Spring Boot) service managing the core business logic, users, and submissions.
*   **[Python Codegen](./platform-codegen):** Python (FastAPI) service responsible for generating challenge assets and repository structures.
*   **[Platform UI](./platform-ui):** React (Vite) frontend providing a high-fidelity IDE experience using WebContainers.
*   **[Gold Master Node](./challenges/book-my-show/apps/gold-master-node):** An example challenge service (Node.js) that simulates a real-world application environment for candidates.

### Infrastructure
- **Databases:** PostgreSQL (Main), Redis (Cache), SQLite (Challenge-local).
- **Messaging:** RabbitMQ for asynchronous job processing.
- **Storage:** S3-compatible storage (MinIO for local development).

## Resilience & Reliability
The platform implements transient error handling across all layers:
- **Backend:** Automatic retries for DB and RabbitMQ connection issues using `spring-retry`.
- **Codegen:** Exponential backoff for Redis operations via `tenacity`.
- **Node Service:** Database transaction retries for `SQLITE_BUSY` errors using `async-retry`.

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Java 21 (for local backend dev)
- Python 3.11 (for local codegen dev)
- Node.js 20+ (for UI and challenge dev)

### Running with Docker
To start the entire platform:
```bash
docker compose up --build
```

Access the UI at: `http://localhost:5173`

## Contribution
Please refer to the [PR Template](.github/pull_request_template.md) for contribution guidelines.
