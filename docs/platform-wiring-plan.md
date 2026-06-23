# Plan: Wire up platform-ui ↔ platform-backend_service ↔ codegen

## Context

platform-ui (student frontend, port 5173), platform-backend_service (student API, port 8080), and platform-codegen (generation service) exist as separately-built services that don't currently communicate. Three classes of gaps:

1. **URL mismatch**: frontend uses `/api/auth/...` and `/api/main/...`; backend exposes `/api/v1/auth/...` and `/api/v1/problems/...`
2. **Missing fields**: challenge responses lack `language` and `zipUrl`; admin-backend never writes `tier` or `language` to the problems table, so the student service can't build the MinIO ZIP path
3. **Missing endpoints**: no draft CRUD, no submission polling, no LLM grading pipeline (platform-workers is a stub with only `llm_evaluator.py`)

---

## Work Stream 1 — platform-ui: Fix API paths + JWT token storage

### `platform-ui/src/store.ts`
Add `token: string | null` to the User interface; persist it on login.

### `platform-ui/src/features/auth/components/Login.tsx` + `Signup.tsx`
- Change `/api/auth/login` → `/api/v1/auth/login`; same for signup
- Backend returns `{ token, userId, email }` — map to store: `{ id: userId, email, name: email, username: email.split('@')[0], token }`
- Signup body: map `{ username, email, password, name }` → `{ email, password, displayName: name }`

### `platform-ui/src/features/workspace/api.ts`
- Add helper `getAuthHeaders()` — reads `token` from Zustand store, returns `{ Authorization: 'Bearer <token>' }` — pass to every authenticated `fetch` call
- `fetchChallenges()`: `GET /api/v1/problems` → backend returns `PageResponse<ProblemSummaryResponse>` — extract `.content`; difficulty values EASY/MEDIUM/HARD pass through (dashboard normalizes them)
- `fetchChallenge(id)`: `GET /api/v1/problems/{id}`
- Draft calls: `/api/main/drafts/...` → `/api/v1/drafts/...`; add auth header; drop `userId` query params (backend extracts from JWT)
- Submit: `POST /api/v1/problems/{challengeId}/submit` with body `{ files }` and auth header → backend returns `{ id }` (HTTP 202) → poll `GET /api/v1/submissions/{id}`

### `platform-ui/src/features/workspace/workspace.types.ts`
- `Challenge.difficulty`: widen to `string` (backend returns EASY/MEDIUM/HARD)
- Add `description?: string` to `Challenge`

### `platform-ui/src/features/dashboard/components/Dashboard.tsx`
Normalize difficulty for badge colors: `EASY → BEGINNER, MEDIUM → INTERMEDIATE, HARD → ADVANCED`.

---

## Work Stream 2 — platform-backend_service: Missing endpoints + MinIO + drafts + submissions

### DB migrations

**`V5__add_language_tier_and_submission_status.sql`**:
```sql
ALTER TABLE problems      ADD COLUMN IF NOT EXISTS language       VARCHAR(16);
ALTER TABLE submissions   ADD COLUMN IF NOT EXISTS status         VARCHAR(16) NOT NULL DEFAULT 'COMPLETED';
ALTER TABLE submissions   ADD COLUMN IF NOT EXISTS feedback_json  TEXT;
ALTER TABLE drafts        ADD COLUMN IF NOT EXISTS files_json     TEXT;
```

### Model updates
- **`Problem.java`**: add `language` field + getter/setter
- **`Submission.java`**: add `status` (default `"COMPLETED"`) and `feedbackJson` TEXT + getters/setters
- **`Draft.java`**: add `filesJson` TEXT field (content store; `draftLink` kept as legacy placeholder)

### MinIO ZIP proxy

**`MinioConfig.java`** (new): `@Bean MinioClient` reading `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`.

**`ChallengeZipController.java`** (new, `/api/v1/problems`):
```
GET /{id}/zip → fetch challenges/{language}/{slug}-{tier}.zip from MinIO
              → stream back as application/zip
              → Cross-Origin-Resource-Policy: cross-origin  ← required for WebContainers fetch
```
Returns 404 if `language` or `tier` is null.

### Response DTO updates
`ProblemSummaryResponse` and `ProblemDetailResponse`: add `language` and `zipUrl` (= `/api/v1/problems/{id}/zip`). Update `ProblemService.toSummary()` / `toDetail()`.

### `SecurityConfig.java`
```java
.requestMatchers("/api/v1/problems/*/zip").permitAll()
.requestMatchers("/api/v1/drafts/**").authenticated()
.requestMatchers("/api/v1/submissions/**").authenticated()
```

### Draft CRUD

**`DraftRepository.java`** (new): `findByUserIdAndProblemId`, `deleteByUserIdAndProblemId`.

**`DraftService.java`** (new): JWT userId extraction via `SecurityContextHolder`; serialize/deserialize `filesJson` via `ObjectMapper`.

**`DraftController.java`** (new, `/api/v1/drafts`):
```
GET    /{problemId}  → 200 { files } or 404
PUT    /{problemId}  → upsert from body { files: Record<string,string> }
DELETE /{problemId}  → 204
```

### Async submission + polling

**`GradingPublisher.java`** (new): RabbitMQ publisher; publishes to `grading-queue`:
```json
{ "submissionId", "problemId", "userId", "filesJson", "remainingTime", "userType" }
```

**`SubmitController.java`** (update):
1. Create `Submission` with `status="PENDING"` in DB immediately
2. Fire virtual-thread task: call execution service (keeps existing bulkhead), then publish to grading-queue
3. Return HTTP 202 `{ "id": submissionId }` without waiting for grading

**`SubmissionController.java`** (new, `/api/v1/submissions`):
```
GET /{id} → { id, status, score, logs, feedback }  — matches GradingResult shape
```

**`application.yml`** additions:
```yaml
app:
  minio:
    endpoint: ${MINIO_ENDPOINT:http://localhost:9000}
    access-key: ${MINIO_ACCESS_KEY:admin}
    secret-key: ${MINIO_SECRET_KEY:password}
    challenges-bucket: ${MINIO_CHALLENGES_BUCKET:challenges}
  grading-queue: ${GRADING_QUEUE:grading-queue}
```

---

## Work Stream 3 — admin-backend: Populate `language` + `tier` on published problems

Admin-backend's `Problem.java` does not have `language` or `tier` columns (the columns exist in the shared DB after the platform-backend V5 migration runs, but admin-backend's JPA entity doesn't map them).

### `admin-backend` `Problem.java`
Add `language` (VARCHAR 16) and `tier` (VARCHAR 64) fields with getters/setters.

### `ProblemManagementService.java` — `createFromJob()`
```java
String language = (job.getLanguages() != null && !job.getLanguages().isEmpty())
    ? job.getLanguages().get(0) : "node";
String tier = deriveTier(job.getResultJson(), job.getTiers());
// after Problem.create(...)
problem.setLanguage(language);
problem.setTier(tier);
```
`deriveTier()`: parse `result_json → manifests → {language} → scenarios[0].tag` for the first scenario of the first tier. Fallback: `"{firstTier}-scenario-1"`.

---

## Work Stream 4 — platform-workers: Build queue consumer

Platform-workers is a stub (only `src/engine/llm_evaluator.py` exists). Build the rest.

### New files
- **`src/config.py`**: `DB_URL`, `REDIS_HOST/PORT`, `MINIO_*`, `RABBITMQ_*`, `ANTHROPIC_API_KEY`, `GRADING_QUEUE`
- **`src/infrastructure/cache.py`**: Redis client; `get_blueprint(problem_id)` reads `blueprint:{problemId}`
- **`src/infrastructure/db.py`**: psycopg2; `update_submission(id, status, score, feedback_json)`
- **`src/queue/consumer.py`**: AMQP consumer on `grading-queue`:
  1. Parse `{ submissionId, problemId, filesJson, remainingTime, userType }`
  2. Fetch blueprint from Redis
  3. Call `LLMEvaluator.evaluate(blueprint, filesJson, remainingTime, userType)`
  4. `db.update_submission(id, "COMPLETED", score, feedback_json)` — or `"FAILED"` on error
- **`src/main.py`**: starts consumer thread
- **`requirements.txt`**: `pika`, `redis`, `psycopg2-binary`, `tenacity`, `anthropic`, `loguru`
- **`Dockerfile`**: Python 3.11 slim

### `docker-compose.yml`
Add `platform-workers` service + add `MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY` to platform-backend_service env.

---

## Verification

```bash
# Build and start
docker compose up --build platform-backend_service platform-workers platform-ui

# Auth smoke test
curl -s -X POST http://localhost:8080/api/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"s@x.com","password":"password123","displayName":"Student"}'

# Challenge list (needs published problems)
curl http://localhost:8080/api/v1/problems

# ZIP proxy (replace {id} with a real problem UUID)
curl -I http://localhost:8080/api/v1/problems/{id}/zip

# Full browser flow:
# http://localhost:5173 → signup → dashboard shows challenges → workspace loads boilerplate → submit → grade result appears
```
