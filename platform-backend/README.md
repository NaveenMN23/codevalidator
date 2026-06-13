# Platform Backend

The core orchestration service for the Scalable Challenge Platform.

## Tech Stack
- **Language:** Java 21
- **Framework:** Spring Boot 3.4.1
- **Database:** PostgreSQL (with Flyway for migrations)
- **Messaging:** Spring AMQP (RabbitMQ)
- **Cache:** Spring Data Redis

## Key Features
- **Challenge Management:** CRUD operations for interview challenges.
- **Submission Pipeline:** Handles candidate submissions and triggers grading jobs asynchronously.
- **Resilience:** Implements `@Retryable` logic for transactional methods to handle transient infrastructure failures.

## Development

### Setup
Ensure you have PostgreSQL, Redis, and RabbitMQ running (e.g., via `docker compose up postgres redis rabbitmq`).

### Run
```bash
./mvnw spring-boot:run
```

### Database Migrations
Migrations are located in `src/main/resources/db/migration`. They run automatically on startup.
