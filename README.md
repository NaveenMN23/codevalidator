# Scalable Challenge Platform

A robust, multi-service platform for hosting and managing technical interview challenges. This platform enables the generation of challenge environments, automated grading, and a seamless browser-based IDE experience.

For a detailed technical breakdown, see the **[Architecture Documentation](./ARCHITECTURE.md)**.

## Key Features
*   **WebContainer IDE:** High-fidelity browser-based coding environment with Node.js support.
*   **WASM-Powered Storage:** Uses WASM SQLite (`sql.js`) for seamless local storage in the browser without native C++ bindings.
*   **Background Installation:** Dependencies install automatically in the background as soon as you enter a challenge.
*   **Modern UI:** Clean, viewport-locked IDE layout with resizable panels and terminal toggling.
*   **Automated Auto-save:** User drafts are saved to the cloud every 2 seconds and isolated per-user.

## Service Map
- **[Platform Backend](./platform-backend):** Java (Spring Boot) managing core logic, users, and asynchronous submissions.
- **[Platform UI](./platform-ui):** React (Vite) frontend providing the "CodeForge" IDE experience.
- **[Platform Workers](./platform-workers):** Python workers performing isolated grading in Docker sandboxes.
- **[Codegen](./platform-codegen):** Service for generating challenge assets from reference repositories.

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for local UI development)
- Java 21 & Python 3.11 (for core service development)

### Running with Docker
```bash
# Start the entire platform
docker compose up --build -d

# Stop the environment
docker compose down

# Rebuild only specific services after changes
docker compose up --build ui backend
```

Access the UI at: `http://localhost:5173`

## Engineering Standards

### 1. User Data Isolation
All persistent data (drafts, submissions) MUST be keyed by `userId`. Cross-user data leakage is a critical security failure.

### 2. Browser Compatibility
All challenge code must be browser-compatible. Native C++ modules (like `better-sqlite3`) are prohibited; use WASM alternatives (like `sql.js`) for local storage.

### 3. Asynchronous Grading
Grading must never block the main request thread. Use the RabbitMQ-based worker flow for all code execution and validation.

### 4. Resilience
External service calls (DB, Redis, RabbitMQ) MUST implement retry patterns (Spring Retry or Tenacity) to handle transient infrastructure blips.
