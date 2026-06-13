# OpenAI / GPT Development Standards

This file provides instructions for OpenAI GPT-based agents working on the Scalable Challenge Platform.

## Core Architectural Mandates

1.  **Service Boundaries:** Maintain clear separation between the Java Backend (Orchestration) and Python Codegen (Generation). Use RabbitMQ for async decoupling.
2.  **Resilience:**
    *   **Java:** Standardize on `spring-retry`.
    *   **Python:** Standardize on `tenacity`.
    *   **Node.js:** Standardize on `async-retry`.
3.  **Clean Root:** Do not add source code or tests to the root directory.
4.  **Docker:** All services must be verifiable via the root `docker-compose.yml`.

## Implementation Rules
*   Follow the `.github/pull_request_template.md`.
*   Maintain `ARCHITECTURE.md` with any structural changes.
*   Ensure the Python `Dockerfile` in `platform-codegen` supports local module imports.

## Stack
- Backend: Java 21, Spring Boot
- Codegen: Python 3.11, FastAPI, Redis
- Challenge: Node.js, Fastify, SQLite
- Frontend: React, Vite, WebContainers
