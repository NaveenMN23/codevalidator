# Platform Backend

The central orchestration service for the Scalable Challenge Platform.

## Tech Stack
- **Language:** Java 21
- **Framework:** Spring Boot 3.4+
- **Database:** PostgreSQL (Relation), Redis (Cache/Fast-persistence)
- **Messaging:** RabbitMQ
- **Versioning:** Flyway

## Key Features
- **Multi-Tenant Draft Service:** User-scoped persistent storage for in-progress work.
- **Asynchronous Grading Dispatch:** Decoupled workflow via RabbitMQ for robust submission handling.
- **Resilience:** Built-in retry logic for DB and Message Broker interactions.
- **Admin API:** Endpoints for challenge management and draft control.

## Standards & Development

### 1. User Isolation
Every draft and submission MUST be keyed by `userId`. Never perform lookups on challenge IDs alone.

### 2. Resilience Pattern
All external service calls (DB, Redis, RabbitMQ) must be wrapped in `@Retryable` to handle transient network issues.

### 3. Asynchronous Results
Grading results are consumed via `GradingResultListener`. The service updates the submission status and scores based on the asynchronous worker output.

## Run with Docker
```bash
docker compose up backend
```
