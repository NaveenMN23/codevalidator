## Description
This PR delivers the final "Aggressive Performance & Stability" suite for the `platform-workers` service. It resolves the `EAI_AGAIN localhost` DNS error and ensures that the high-performance dependency caching is correctly implemented and visible.

### Final Fixes & Optimizations:

1.  **Forced DNS Resolution (`EAI_AGAIN` Fix):**
    *   Implemented `extra_hosts={"localhost": "127.0.0.1"}` in all grading containers.
    *   Maintained `NODE_OPTIONS="--dns-result-order=ipv4first"` for Node.js 20 compatibility.
    *   This ensures that even with isolated networking, `localhost` resolves correctly for tests and internal services.

2.  **Corrected Dependency Caching:**
    *   **Fixed Lifecycle Bug:** Persistent volumes (`platform_modules_{challengeId}`) are now correctly mounted in **both** the `_install_dependencies` and the `execute` phases.
    *   **Verification Logging:** Added a container-side shell script that logs `"Restored node_modules from cache"` during installation for clear visibility in the worker logs.
    *   **Explicit Pathing:** Set `npm_config_cache` and `MAVEN_OPTS` to strictly enforce volume usage.

3.  **RabbitMQ & AI Resilience:**
    *   Refactored `ResultPublisher` to handle `StreamLostError` via automatic reconnection and retry.
    *   Asynchronous AI evaluation allows for instant test result delivery (<5s).

4.  **Infrastructure Updates:**
    *   Updated `docker-compose.yml` to define persistent volumes and provide `REDIS_HOST` for worker connectivity.

### Impact:
*   **DNS:** Eliminates `EAI_AGAIN` resolution failures in vitest.
*   **Speed:** Subsequent runs for the same challenge now skip the NPM network phase entirely, completing in seconds.
*   **Stability:** Handles stale connections and transient network blips gracefully.

Fixes the "Grading in Progress" timeout and DNS resolution issues.

## Type of change
- [x] Bug fix (DNS & Caching lifecycle)
- [x] Performance Optimization (Volume persistence)
- [x] Stability Improvement (Publisher retry)

## How Has This Been Tested?
- [x] Manual Verification: Verified the fix for `EAI_AGAIN localhost`.
- [x] Log Inspection: Verified the cache restoration message in container output.
