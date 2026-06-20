# Plan: Admin UI + Admin Service + Preview-then-Generate Flow

## Context

The platform currently has no dedicated admin experience. Challenge generation is triggered
via a raw POST to codegen that blocks for 5–15 minutes with no feedback. The user wants:

1. **Separate admin-service** (Java Spring Boot 3) — admin API isolated from the student-facing platform-backend
2. **Separate admin-ui** (React/Vite) — admin dashboard isolated from the student platform-ui
3. **Preview flow** — admin describes a challenge, sees a human-readable preview of all 9 scenarios (3 per tier) before committing to expensive generation
4. **Queue-based generation** — full generation published to RabbitMQ; codegen consumes asynchronously; admin polls for job status

---

## Architecture

```
admin-ui (React, :5174)
      │  POST /api/admin/challenges/preview   ← Phase 1 only, sync (~30–60 s)
      │  POST /api/admin/challenges/generate  ← enqueues job, returns jobId
      │  GET  /api/admin/jobs/{id}            ← poll for status
      ▼
admin-service (Spring Boot 3, :8081)
      │  HTTP → platform-codegen /preview     (Phase 1 — design only)
      │  publishes → generation-jobs queue
      │  listens  ← generation-results queue  (updates job row)
      ▼
RabbitMQ
      │  generation-jobs queue
      ▼
platform-codegen
      │  queue consumer → scaffold_generator.generate()
      │  publishes → generation-results queue
```

**Queues added to RabbitMQ:**
- `generation-jobs` — admin-service publishes, codegen consumes
- `generation-results` — codegen publishes completion/failure, admin-service listens

---

## New Service: `admin-service` (Java Spring Boot 3)

### Location
`/admin-service/` at the repo root — peer to `platform-backend/`.

### Key files

**`pom.xml`** — spring-boot-starter-web, spring-boot-starter-data-jpa, spring-boot-starter-amqp,
postgresql, flyway-core, lombok, spring-retry, spring-boot-starter-test

**`src/main/resources/application.properties`**
```properties
spring.application.name=admin-service
server.port=8081
spring.datasource.url=jdbc:postgresql://localhost:5432/interview_db
spring.jpa.hibernate.ddl-auto=none
spring.flyway.enabled=true
# RabbitMQ, Redis same as platform-backend
```

**`V1__admin_generation_jobs.sql`**
```sql
CREATE TABLE admin_generation_jobs (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  status       VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  language     VARCHAR(20) NOT NULL DEFAULT 'node',
  problem_description TEXT  NOT NULL,
  challenge_name      VARCHAR(200),
  preview_data        JSONB,          -- Phase 1 DesignOutput stored here
  error_message       TEXT,
  created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);
-- status values: PENDING | PROCESSING | COMPLETED | FAILED
```

**`RabbitMQConfig.java`**
```java
public static final String GENERATION_JOBS_QUEUE    = "generation-jobs";
public static final String GENERATION_RESULTS_QUEUE = "generation-results";
public static final String ADMIN_EXCHANGE           = "admin-exchange";
public static final String GENERATION_ROUTING_KEY   = "generation.key";
// declare both queues + exchange + bindings + Jackson2JsonMessageConverter
```

**`GenerationJob.java`** (JPA entity mapping `admin_generation_jobs`)

**`ChallengeController.java`** — `@RestController @RequestMapping("/api/admin/challenges")`
- `POST /preview` → calls codegen `/preview` via `RestTemplate` (120s timeout), stores preview in job row, returns readable `PreviewResponse`
- `POST /generate` → creates job row (PENDING), publishes `GenerationJobMessage` to RabbitMQ, returns `{ jobId }`
- `GET /` → list all jobs with status

**`JobController.java`** — `@RestController @RequestMapping("/api/admin/jobs")`
- `GET /{id}` → return job status + challenge_name + error

**`ChallengeGenerationService.java`**
- `previewChallenge(req)` — HTTP to codegen, parse response, persist preview JSON, return `PreviewResponse`
- `enqueueGeneration(jobId, req)` — publish RabbitMQ message, update row to PENDING

**`GenerationResultListener.java`** — `@RabbitListener(queues = GENERATION_RESULTS_QUEUE)`
- On success: update job row → COMPLETED, set challenge_name
- On failure: update job row → FAILED, set error_message

**DTOs:**
```java
// Sent to RabbitMQ
record GenerationJobMessage(UUID jobId, String problemDescription, String language) {}

// Returned from /preview
record PreviewResponse(
    String challengeName,
    String challengeDescription,
    List<TierPreview> tiers
) {}
record TierPreview(String tier, List<ScenarioPreview> scenarios) {}
record ScenarioPreview(String tag, String title, String description) {}
```

**Dockerfile** — same pattern as platform-backend (multi-stage Maven build)

---

## New Service: `admin-ui` (React + Vite + TypeScript)

### Location
`/admin-ui/` at the repo root — peer to `platform-ui/`.

### Pages and components

**`/` — Dashboard**
- Table of all jobs: status badge, challenge name, language, created time
- "New Challenge" button → navigates to `/challenges/new`
- Auto-refreshes every 10s while any job is PENDING/PROCESSING

**`/challenges/new` — New Challenge (3-step flow)**

Step 1 — Describe:
- Textarea: problem description
- Dropdown: language (Node.js / Java / Python)
- "Preview Scenarios" button → calls `POST /api/admin/challenges/preview`
- Shows a spinner with "Generating preview (30–60 s)…"

Step 2 — Preview:
- Three accordion sections: EASY / MEDIUM / HARD
- Each section shows 3 scenario cards with `title` + `description` in plain readable prose
- No JSON exposed to the admin
- Two buttons: "← Back" and "Approve & Generate →"

Step 3 — Generating:
- Shows job ID + polling status every 5s (`GET /api/admin/jobs/{id}`)
- PENDING → spinning indicator
- PROCESSING → progress bar (indeterminate)
- COMPLETED → success panel with challenge name + link to challenges list
- FAILED → error message

**`/jobs/:id` — Job Detail** (deep-link to step 3 for any job)

**Key components:**
- `ScenarioCard` — title heading + description text
- `TierSection` — collapsible panel with 3 ScenarioCards
- `StatusBadge` — colour-coded chip (grey/blue/green/red)
- `api.ts` — typed fetch wrappers for all admin-service endpoints

**`Dockerfile`** — Vite build → nginx static serve (same pattern as platform-ui)

---

## Changes to `platform-codegen`

### New endpoint in `api/routes.py`

```python
@router.post("/preview")
async def preview_challenge(request: GoldenRepoRequest):
    """Phase 1 only — returns readable scenario design without triggering generation."""
    try:
        clean = sanitizer.sanitize_description(request.prompt)
        design_system = llm_client.load_prompt("design_challenge")
        raw = llm_client.complete_json(
            design_system,
            f"<language>{request.language}</language>\n<problem>\n{clean}\n</problem>",
            label="preview-design",
        )
        design = validate_with_correction(raw, DesignOutput, llm_client.complete_json,
                                          design_system, ..., label="preview-validate")
        return _design_to_preview(design)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

`_design_to_preview(design: DesignOutput) -> dict` — converts to the readable structure:
```json
{
  "challenge": { "name": "...", "description": "..." },
  "tiers": [
    { "tier": "easy", "scenarios": [{ "tag": "...", "title": "...", "description": "..." }] },
    { "tier": "medium", "scenarios": [...] },
    { "tier": "hard",   "scenarios": [...] }
  ]
}
```

### New queue consumer: `infrastructure/generation_consumer.py`

```python
class GenerationConsumer:
    def __init__(self): ...

    def start(self):
        # pika BlockingConnection, declare generation-jobs queue
        # basic_consume(on_message_callback=self._handle)
        # channel.start_consuming() in a daemon thread

    def _handle(self, ch, method, props, body):
        msg = json.loads(body)      # { jobId, problemDescription, language }
        try:
            scaffold_generator.generate(msg["problemDescription"], msg["language"])
            self._publish_result(msg["jobId"], success=True, challengeName=...)
        except Exception as e:
            self._publish_result(msg["jobId"], success=False, error=str(e))
        ch.basic_ack(delivery_tag=method.delivery_tag)
```

Started as a **daemon thread** when FastAPI app starts (in `main.py` lifespan hook or
startup event). Uses `tenacity` retry for the pika connection (`stop_after_attempt(3),
wait_exponential`).

### `config/settings.py` additions
```python
rabbitmq_host: str = "localhost"
rabbitmq_port: int = 5672
rabbitmq_user: str = "admin"
rabbitmq_password: str = "password"
generation_jobs_queue: str = "generation-jobs"
generation_results_queue: str = "generation-results"
```

---

## Changes to `docker-compose.yml`

```yaml
  admin-service:
    build: ./admin-service
    container_name: platform_admin_service
    ports:
      - "8081:8081"
    environment:
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/interview_db
      SPRING_DATASOURCE_USERNAME: admin
      SPRING_DATASOURCE_PASSWORD: password
      SPRING_RABBITMQ_HOST: rabbitmq
      SPRING_RABBITMQ_USERNAME: admin
      SPRING_RABBITMQ_PASSWORD: password
      CODEGEN_URL: http://codegen:8000
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      codegen:
        condition: service_started

  admin-ui:
    build: ./admin-ui
    container_name: platform_admin_ui
    ports:
      - "5174:80"
    depends_on:
      - admin-service
```

Add `RABBITMQ_*` env vars to `codegen` service so the generation consumer can connect.

---

## Files to create / modify

| Path | Action |
|---|---|
| `admin-service/` | CREATE — full Spring Boot project |
| `admin-ui/` | CREATE — full React/Vite project |
| `platform-codegen/api/routes.py` | ADD `/preview` endpoint + `_design_to_preview` helper |
| `platform-codegen/infrastructure/generation_consumer.py` | CREATE — pika consumer daemon thread |
| `platform-codegen/config/settings.py` | ADD RabbitMQ settings |
| `platform-codegen/main.py` | ADD consumer startup in lifespan hook |
| `docker-compose.yml` | ADD admin-service + admin-ui services; add RabbitMQ env to codegen |

---

## Refinement Flow (deferred — implement after core flow is working)

When the preview doesn't match expectations the admin has two options (both supported):

### A — Inline edit individual scenarios
- Each scenario card in the preview has an "Edit" button
- Admin edits title and/or description inline
- Changes saved locally in component state
- "Approve & Generate" sends the edited `preview_data` to the generate endpoint
- No extra LLM call — zero cost

### B — Feedback note + re-generate
- Below the preview panel: "Refinement note" textarea
  - e.g. *"Make the HARD tier focus on Redis caching, not circuit breakers"*
- "Re-generate Preview" button → `POST /api/admin/challenges/preview` with original `prompt` + `feedback`
- admin-service forwards both to codegen `/preview`
- codegen Phase 1 appends `<feedback>{feedback}</feedback>` to the user context
- New design shown; admin can keep re-generating or switch to inline editing

### Implementation touch-points (small additions to the core plan above)
| Component | Change |
|---|---|
| `PreviewRequest` DTO | Add `String feedback` (nullable) |
| `POST /preview` in codegen | Accept optional `feedback`, append to user context if present |
| `admin-ui ScenarioCard` | Add Edit mode (controlled input for title + description) |
| `admin-ui NewChallenge` | Add refinement textarea + "Re-generate" button |
| `POST /generate` admin-service | Accept optional `previewData` override; if present, store it in job row and skip Phase 1 re-run |

---

## Verification

1. `docker compose up --build admin-service admin-ui codegen`
2. Open `http://localhost:5174` → admin dashboard loads
3. Click "New Challenge", enter description, click "Preview Scenarios"
4. Verify preview shows 3 tiers × 3 scenario cards in readable prose (no JSON)
5. Click "Approve & Generate" → job row created, RabbitMQ message published
6. Codegen picks up job, runs full generation (~5-15 min)
7. Poll `GET /api/admin/jobs/{id}` → transitions PENDING → PROCESSING → COMPLETED
8. Dashboard auto-refreshes and shows completed challenge
