# Platform Codegen — Architecture & Logic Reference

> **Service:** `platform-codegen` · FastAPI · Python 3.11 · Port 8000
>
> This document captures the full logic of the code generation pipeline so it can be
> understood, debugged, or extended without reading every source file from scratch.

---

## Table of Contents

1. [What it does](#1-what-it-does)
2. [Directory structure](#2-directory-structure)
3. [Generation pipeline — the three phases](#3-generation-pipeline--the-three-phases)
4. [Skeleton + Delta architecture](#4-skeleton--delta-architecture)
5. [LLM prompts](#5-llm-prompts)
6. [Validation and correction loop](#6-validation-and-correction-loop)
7. [Storage — MinIO layout](#7-storage--minio-layout)
8. [Local export (dev only)](#8-local-export-dev-only)
9. [Blueprint generation (Phase 3)](#9-blueprint-generation-phase-3)
10. [LLM client — cost tracking](#10-llm-client--cost-tracking)
11. [Configuration reference](#11-configuration-reference)
12. [API endpoints](#12-api-endpoints)
13. [Data flow diagram](#13-data-flow-diagram)

---

## 1. What it does

Given a plain-English problem description (e.g. *"Build a vending machine API"*) and a
target language, the codegen service generates:

| Output | Count | Stored in |
|---|---|---|
| Student scaffold ZIP (stubs intact) | 9 (3 tiers × 3 scenarios) | MinIO `challenges/` bucket |
| Gold master ZIP (full implementation + hidden tests) | 3 (one per tier) | MinIO `gold-masters/` bucket |
| Blueprint (AI evaluation rubric) | 9 | Postgres + Redis |
| Local extracted files (dev only) | 9 scaffolds + 3 gold masters | `generated/` on host |

Everything is generated from scratch with no hand-written templates. The LLM is the
only author.

---

## 2. Directory structure

```
platform-codegen/
  api/
    routes.py               ← FastAPI router (POST /admin/generate-golden-repo, GET /health)
  config/
    settings.py             ← Pydantic settings (env vars)
  generator/
    engine.py               ← ZIP builder (generate_from_dict → scaffold ZIP)
  infrastructure/
    cache.py                ← Redis client
    logger.py               ← Loguru logger
    storage.py              ← S3/MinIO client (upload, download, local export)
  prompts/                  ← .mdx LLM prompt files (YAML frontmatter + body)
    design_challenge.mdx
    implement_skeleton_node.mdx
    implement_skeleton_java.mdx
    implement_skeleton_python.mdx
    implement_function_node.mdx
    implement_function_java.mdx
    implement_function_python.mdx
    generate_blueprint.mdx
    design_challenge.mdx
  services/
    llm.py                  ← OpenAI client wrapper (cost tracking, retries)
    sanitizer.py            ← Input/output sanitizer
    scaffold_generator.py   ← Main orchestrator (3-phase pipeline)
    blueprint.py            ← Blueprint generation (Phase 3)
    validators.py           ← Pydantic output models + correction loop
  main.py                   ← FastAPI app entry point
```

---

## 3. Generation pipeline — the three phases

Entry point: `ScaffoldGenerator.generate(problem_description, language)`
Called from: `POST /admin/generate-golden-repo`

### Phase 1 — Architecture Design (1 LLM call)

**Prompt:** `design_challenge.mdx`
**Output model:** `DesignOutput`

Produces a full challenge design document:
```json
{
  "challenge": { "name": "vending-machine", "description": "..." },
  "entities": [...],
  "difficulty_tiers": {
    "easy":   { "scenarios": [ { "scenario_tag": "easy-dispense-product", "title": "...", "description": "...", "strip_description": "..." }, ... ] },
    "medium": { "scenarios": [...] },
    "hard":   { "scenarios": [...] }
  }
}
```

Each tier has exactly 3 scenarios. Each scenario has:
- `scenario_tag` — slug used as the identifier everywhere (e.g. `easy-dispense-product`)
- `title` — human-readable name shown to the student
- `description` — what the student needs to implement
- `strip_description` — detailed spec used by Phase 2b to implement the function body

---

### Phase 2a — Skeleton generation (3 LLM calls, one per tier)

**Prompt:** `implement_skeleton_{language}.mdx`
**Output model:** `SkeletonOutput`
**Token limit:** `openai_max_tokens_impl` (16 384)

For each tier, generates a **complete codebase** where:
- All non-target functions are **fully implemented** (they serve as pattern examples)
- Each target function (one per scenario) contains **only** a stub:
  - Node: `throw new Error('not implemented: easy-dispense-product');`
  - Java: `throw new UnsupportedOperationException("not implemented: easy-dispense-product");`
  - Python: `raise NotImplementedError("not implemented: easy-dispense-product")`

Output schema:
```json
{
  "files": { "src/index.ts": "...", "src/db.ts": "...", ... },
  "stub_locations": {
    "easy-dispense-product": { "file": "src/handlers/vending.ts", "function_name": "dispenseProduct" }
  }
}
```

**Why one skeleton per tier (not per scenario)?**
All 3 scenarios in a tier share the same skeleton. Each scenario's stub is present in the
skeleton simultaneously. This means the student scaffold for `easy-dispense-product` has
stubs for ALL easy-tier target functions, not just their own — preventing cross-contamination
(students can't see another scenario's answer in their scaffold).

---

### Phase 2b — Function delta generation (3 × N LLM calls)

**Prompt:** `implement_function_{language}.mdx`
**Output model:** `FunctionDeltaOutput`
**Token limit:** `openai_max_tokens_test` (8 192) — larger because HARD tests have 70+ assertions

For each scenario, generates:
1. `function_body` — the complete implementation of the stubbed function (statements only,
   no signature or closing brace)
2. `test_hidden` — a comprehensive hidden test file scaled to the tier

**Hidden test assertion targets:**

| Tier | Min assertions | Min test functions |
|---|---|---|
| EASY | 40 | 10 |
| MEDIUM | 50 | 15 |
| HARD | 70 | 20 |

**Test categories covered (all tiers):** happy path, 404 not-found, 403 forbidden,
400 validation, boundary values, state consistency, idempotency.

**Additional for MEDIUM:** partial data, type edge cases.

**Additional for HARD:** concurrency hints, infrastructure state (cache/lock/circuit),
cascading failures.

---

### Assembly — Gold master and scaffold

After Phase 2a and 2b complete, for each tier:

**Gold master** = skeleton files with ALL N function bodies injected back in:
```python
gold_master_files = _inject_all_deltas(skeleton.files, deltas, language, skeleton)
```
Uploaded to `gold-masters/{language}/{challenge}-{tier}.zip` containing:
- `manifest.json` — challenge metadata + scenario list
- `src/` — fully implemented source files
- `test-hidden/hidden-{tag}.{ext}` — one hidden test per scenario

**Student scaffold** = skeleton unchanged (stubs as-is) + scenario-specific README.
One ZIP per scenario uploaded to `challenges/{language}/{challenge}-{scenario-tag}.zip`.

---

### Phase 3 — Blueprint generation (3 × N LLM calls)

**Prompt:** `generate_blueprint.mdx`

For each scenario, generates an AI evaluation rubric (blueprint) used by the grading
workers to give qualitative feedback on passing submissions. Dispatched to
`platform-backend` via HTTP and cached in Redis.

---

## 4. Skeleton + Delta architecture

### The cross-contamination problem

Without this architecture, each scenario would get its own gold master with only its
own function implemented. If a student in scenario A has a scaffold that also includes
scenario B's implemented function (because they share a file), they could see B's answer.

### The solution

- **One skeleton per tier** — all N target functions are stubs in the same codebase
- **Student scaffold = skeleton unchanged** — every student's scaffold has ALL target
  functions as stubs, so no scenario reveals another's implementation
- **Gold master = skeleton + all N deltas injected** — used for grading and blueprints only

### Delta injection

`_inject_all_deltas(skeleton_files, deltas, language, tier_skeleton)`:

1. **Exact match** (preferred): looks for `throw new Error('not implemented: {tag}');`
   and replaces it with `delta.function_body`
2. **Regex fallback**: if the LLM used a slightly different stub message (accepted by the
   level-2 validator), uses `_replace_function_body()` to find the function by name via
   brace-counting (Node/Java) or indentation (Python) and replace its body

---

## 5. LLM prompts

All prompts live in `prompts/` as `.mdx` files with YAML frontmatter. `LLMClient.load_prompt(name)`
strips the frontmatter and returns the body as the system prompt.

| Prompt file | Phase | Calls per generation |
|---|---|---|
| `design_challenge.mdx` | 1 | 1 |
| `implement_skeleton_{lang}.mdx` | 2a | 3 (one per tier) |
| `implement_function_{lang}.mdx` | 2b | 9 (3 tiers × 3 scenarios) |
| `generate_blueprint.mdx` | 3 | 9 (one per scenario) |

**Total LLM calls per full generation: ~22** (1 + 3 + 9 + 9)

Phase 2a uses `complete_json_cached()` — the static skeleton prompt is in the system
message, enabling OpenAI prefix caching across the 3 tier calls (~50% token cost reduction
on cached prefixes > 1 024 tokens).

Phase 3 also uses prefix caching — the gold master source code is in the system message,
shared across 3 scenario blueprint calls per tier.

---

## 6. Validation and correction loop

`validate_with_correction(raw, model_cls, llm_call, system, user, label)` in `validators.py`:

1. Parse JSON from LLM response
2. Validate against Pydantic model
3. On failure: send a correction prompt back to the LLM with the validation error
4. Retry up to `MAX_CORRECTION_ATTEMPTS = 3` times
5. Raise `ValueError` if all attempts fail

### `SkeletonOutput` validator — two-level stub check

**Level 1 (exact):** `"not implemented: {tag}"` found anywhere in the files → pass.

**Level 2 (function-present fallback):** If exact match fails, check that the file
named in `stub_locations` contains the function name AND a throw/raise statement. Accept
with a warning log. This handles LLMs that use a slightly different stub message.
`_inject_all_deltas` uses the regex fallback for injection in this case.

### Output models

| Model | Validates |
|---|---|
| `DesignOutput` | 3 tiers, 3 scenarios each, required fields |
| `SkeletonOutput` | files not empty, all stub markers present (two-level) |
| `FunctionDeltaOutput` | function_body not empty, test_hidden not empty |
| `GoldMasterOutput` | legacy, kept for backward compatibility |

---

## 7. Storage — MinIO layout

Two buckets:

### `challenges/` (public read)
Student scaffold ZIPs — downloaded by students when they open a challenge.
```
challenges/
  node/
    {challenge}-{scenario-tag}.zip
      README.md                    ← scenario-specific task description
      src/                         ← all source files with target function as stub
      package.json
      tsconfig.json
  java/
  python/
```

### `gold-masters/` (private)
Full implementation + hidden tests — fetched only by grading workers.
```
gold-masters/
  node/
    {challenge}-{tier}.zip
      manifest.json                ← { challenge, language, scenarios: { tag: { title, description, tier } } }
      src/                         ← fully implemented source files
      test-hidden/
        hidden-{scenario-tag}.test.ts   ← hidden test file (one per scenario)
  java/
  python/
```

### Workers' tri-partite cache

`GoldMasterStorage` in `platform-workers` downloads a gold master ZIP once per
`(challenge, tier, language)` tuple and caches all three sections in memory:
- `tests` — `{ filename: content }` — hidden test files
- `manifest` — parsed manifest dict
- `src` — `{ rel_path: content }` — source files

---

## 8. Local export (dev only)

When `LOCAL_EXPORT_PATH=/generated` is set (Docker bind mount in dev), after every
MinIO upload the service also writes to the local filesystem:

```
generated/
  dist/
    challenges/{language}/{challenge}-{scenario-tag}.zip   ← scaffold ZIPs (MinIO mirror)
    gold-masters/{language}/{challenge}-{tier}.zip          ← gold master ZIPs (MinIO mirror)
  {challenge}/
    {language}/
      scaffold/
        {scenario-tag}/            ← extracted scaffold (browsable without unzipping)
          src/
          README.md
          package.json
      gold-master/
        {tier}/                    ← extracted reference implementation (no hidden tests)
          manifest.json
          src/
```

`dist/` mirrors MinIO bucket structure exactly — `minio-setup` uses `mc mirror` to
re-seed MinIO from `generated/dist/` on `docker compose up`, so a MinIO wipe doesn't
require re-running generation.

**In production** (real AWS S3): `LOCAL_EXPORT_PATH` is unset → no local export.

---

## 9. Blueprint generation (Phase 3)

`BlueprintService.generate_all_scenarios(challenge_name, language, manifest)`:

1. Fetches gold master source once per tier (3 MinIO downloads for 9 scenarios)
2. For each scenario:
   - Builds repo context string from source files (up to 60 000 tokens, priority-ordered
     by route/service/handler files)
   - Puts static context (instructions + source) in system message → prefix cache hit
   - Puts dynamic scenario description in user message
   - Calls `generate_blueprint.mdx` prompt
3. Embeds relevant source files (`goldMasterSource`) into the blueprint for the worker
4. Dispatches each blueprint to `platform-backend POST /api/admin/blueprints` for
   Postgres storage and Redis caching

Blueprints are used by `platform-workers` during AI evaluation of premium submissions.

---

## 10. LLM client — cost tracking

`LLMClient` in `services/llm.py` wraps all OpenAI calls with:

- **Retry:** 3 attempts, exponential backoff (tenacity)
- **Token budget warning:** logs a warning if estimated input > 80 000 tokens
- **Cost tracking per call:**

```
[skeleton-hard] tokens — prompt: 3503 (cached: 3072), completion: 3288, total: 6791 | cost: $0.0339 (session total: $0.0821)
```

**Pricing table** (`_PRICE_PER_1M`):

| Model | Input | Cached input | Output |
|---|---|---|---|
| gpt-4o | $2.50 | $1.25 | $10.00 |
| gpt-4o-mini | $0.15 | $0.075 | $0.60 |

`reset_session_cost()` is called at the start of each `generate()` call.
At the end of `generate()`, the final session total is logged alongside the complete
token breakdown (input / cached / output).

---

## 11. Configuration reference

All settings read from environment variables (or `.env` file).

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | `""` | Required for LLM calls |
| `OPENAI_MODEL` | `gpt-4o` | Model for all generation calls |
| `OPENAI_TEMPERATURE` | `0.2` | Low for deterministic output |
| `OPENAI_MAX_TOKENS` | `4096` | Default token limit |
| `OPENAI_MAX_TOKENS_IMPL` | `16384` | Phase 2a skeleton (large file trees) |
| `OPENAI_MAX_TOKENS_TEST` | `8192` | Phase 2b hidden tests (HARD tier = 70+ assertions) |
| `MINIO_ENDPOINT` | `http://localhost:9000` | S3-compatible endpoint; unset for AWS S3 |
| `MINIO_ACCESS_KEY` | `admin` | S3 access key |
| `MINIO_SECRET_KEY` | `password` | S3 secret key |
| `MINIO_BUCKET` | `challenges` | Bucket for student scaffold ZIPs |
| `REDIS_HOST` | `localhost` | Redis for blueprint caching |
| `BACKEND_URL` | `http://platform-backend:8080` | Platform backend for blueprint dispatch |
| `LOCAL_EXPORT_PATH` | `""` | Dev bind-mount path; empty = disabled |
| `ENABLE_BLUEPRINT_GENERATION` | `true` | Feature flag — skip Phase 3 if false |
| `ENABLE_LLM` | `true` | Master LLM kill-switch |

---

## 12. API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/generate-golden-repo` | Full 3-phase generation (blocking, ~5–15 min) |
| `GET` | `/health` | Health check |

**Request body for `/admin/generate-golden-repo`:**
```json
{ "prompt": "Build a vending machine REST API...", "language": "node" }
```
`language` must be one of `node`, `java`, `python`.

**Response:**
```json
{ "challenge": "vending-machine", "language": "node", "manifest": { ... } }
```

---

## 13. Data flow diagram

```
Admin
  │  POST /admin/generate-golden-repo { prompt, language }
  ▼
FastAPI router (routes.py)
  │  sanitize input
  ▼
ScaffoldGenerator.generate()
  │
  ├── Phase 1: LLM → DesignOutput (1 call)
  │     design_challenge.mdx
  │     → { challenge, difficulty_tiers: { easy/medium/hard: { scenarios: [3] } } }
  │
  ├── Phase 2a: LLM × 3 → SkeletonOutput per tier
  │     implement_skeleton_{lang}.mdx
  │     → { files: { path: content }, stub_locations: { tag: { file, function_name } } }
  │     All N target functions are stubs; non-target functions fully implemented
  │
  ├── Phase 2b: LLM × 9 → FunctionDeltaOutput per scenario
  │     implement_function_{lang}.mdx  (with <tier> for test depth scaling)
  │     → { function_body: "...", test_hidden: "..." }
  │
  ├── Assembly (in-memory, no LLM):
  │     gold_master  = skeleton + all N deltas injected
  │     scaffold_zip = skeleton unchanged + scenario README
  │
  ├── MinIO uploads:
  │     gold-masters/{lang}/{challenge}-{tier}.zip  × 3
  │     challenges/{lang}/{challenge}-{tag}.zip     × 9
  │
  ├── Local export (dev only, if LOCAL_EXPORT_PATH set):
  │     generated/dist/...     ← ZIP mirror for MinIO re-seeding
  │     generated/{challenge}/ ← extracted browsable files
  │
  └── Phase 3: LLM × 9 → blueprints
        generate_blueprint.mdx (prefix-cached per tier)
        → dispatched to platform-backend POST /api/admin/blueprints
        → stored in Postgres + Redis

Workers (grading pipeline):
  MinIO gold-masters/{lang}/{challenge}-{tier}.zip
    → tri-partite cache: { tests, manifest, src }
    → inject locked files + hidden tests into student staging dir
    → run tests in Docker sandbox
    → AI eval (premium only) using blueprint from Redis
```
