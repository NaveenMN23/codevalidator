# Evaluation Engine Design

`platform-eval` is the AI-powered interviewer for the Scalable Challenge Platform. It conducts a
structured, interactive technical interview after a candidate's code submission passes automated tests.

---

## 1. Core Principles

| Principle | Implementation |
|---|---|
| **LLM rates, service scores** | The LLM emits 1–10 ratings per dimension. The service computes the final weighted score deterministically — the model never sees or emits a finalScore. |
| **Interactive, not robotic** | Every LLM turn begins with an acknowledgment of what the candidate did, then asks exactly one follow-up question. The interview feels like a conversation, not a grading form. |
| **Concept-aware sequencing** | The service tracks which blueprint focus areas have already been probed. The LLM is always directed to a fresh, prioritised area — no repeated probing. |
| **Time-budget-aware** | Available time controls how many turns to budget, what formats are allowed, and whether to escalate or close. No LLM call is wasted on a session about to be force-closed. |
| **Guardrails over trust** | LLM follow-up output is validated against the policy matrix (format legality, area scope). A deterministic fallback replaces any output that fails the guardrail. |

---

## 2. Architecture

```
Java backend (platform-backend)
  │
  │  POST /eval/submit         (after all tests pass)
  │  POST /eval/answer         (candidate's conversational answer)
  │  GET  /eval/session/{id}   (read-only state poll)
  ▼
platform-eval (FastAPI, Python)
  │
  ├── api/routes.py            — request validation, HTTP error mapping
  ├── services/eval_core.py    — per-turn orchestrator
  ├── services/steering.py     — deterministic policy matrix
  ├── services/session_manager.py  — session CRUD, reconciliation, scoring
  ├── services/interviewer.py  — LLM prompt builder
  ├── services/llm_client.py   — OpenAI wrapper (retry, cost logging)
  ├── services/sources.py      — blueprint + gold-master resolver
  ├── models/dtos.py           — all request/response/state models
  ├── config/score_profiles.py — weighted scoring by difficulty
  └── infrastructure/
        ├── store.py           — Postgres write-through + Redis hot cache
        └── cache.py           — Redis client with tenacity retry
```

Communication with Java is **synchronous REST** — a deliberate exception to the platform's
RabbitMQ-first rule. An interactive human-in-the-loop interview has the opposite shape from
fire-and-forget work.

---

## 3. Session Lifecycle

### 3.1 State Machine

```
[code submitted, tests pass]
         │
         ▼
  INITIAL_SUBMISSION ──────────────────────────────────────────┐
         │                                                      │
         │ (LLM generates follow-up)                           │
         ▼                                                      │
FOLLOWUP_CONVERSATIONAL  ◄──────────────────────────────┐      │
         │                                               │      │
         │ (LLM generates another conversational q)      │      │
         ▼                                               │      │
   [candidate answers]  ─────────────────────────────────┘      │
         │                                                      │
         │ (LLM decides IMPLEMENTATION follow-up)               │
         ▼                                                      │
FOLLOWUP_IMPLEMENTATION ─────────────────────────────────────────┘
         │
         │ (candidate re-submits code, eval loops)
         ▼
      CLOSED  (report generated)
```

### 3.2 Close Conditions

A session closes when **any** of the following are true:

| Condition | Source |
|---|---|
| `time_remaining ≤ min_time` | Time gate — fires before any LLM call |
| `turn_count ≥ max_turns` | Dynamic budget (see §5) |
| `candidate_depth == STRONG` | LLM assessed candidate as fully proficient |
| `follow_up_intent == CLOSE` | Policy matrix decided no more questions |
| LLM returned `follow_up: null` | LLM chose to close |

### 3.3 SessionState Fields

```python
session_id: str
problem_id: str
stage: Stage                    # INITIAL_SUBMISSION | FOLLOWUP_CONVERSATIONAL | FOLLOWUP_IMPLEMENTATION
active_follow_up: FollowUp      # the question currently pending an answer
conversation_history: list[ConversationTurn]  # full INTERVIEWER/CANDIDATE transcript
submissions: list[SubmissionRecord]           # code submissions with correctness/efficiency ratings
answer_ratings: list[int]       # 1-10 rating per conversational answer
probed_areas: list[str]         # focus area names already asked (prevents repetition)
concept_scores: dict[str,int]   # area → answer_rating from the answered question
concept_findings: dict[str,str] # area → LLM finding text
turn_count: int
closed: bool
report: EvalReport
start_time_seconds: int
```

---

## 4. Per-Turn Flow (eval_core.py)

Every call to `/eval/submit` or `/eval/answer` follows the same pipeline:

```
1. RESOLVE      blueprint (Redis → Postgres → local FS)
                gold-master files (S3 zip or local zip)
2. TIME GATE    if time_remaining ≤ min_time → force close, no LLM call
3. BUDGET       compute_max_turns(time_remaining, min_time, difficulty)
4. STEER        select_intent_and_formats(...)  → (intent, legal_formats)
5. BUILD        interviewer.build_*_messages(...)  → (system_prompt, user_message)
6. CALL         llm_client.complete_json[_cached](...)  → raw dict
7. VALIDATE     CodeEvalOutput.model_validate(raw)
                validate_follow_up(format, intent, legal_formats, open_areas, chosen_area)
                  → fallback if fails guardrail
8. RECONCILE    session_manager.reconcile_*(...)
                  → update probed_areas, concept_scores, session stage
9. PERSIST      session_store.save(session)
10. RESPOND     CodeSubmitResponse / ConversationalAnswerResponse
```

The system prompt contains the stable prefix (persona + blueprint + gold-master) so OpenAI prefix
caching applies on turns 2+, reducing token cost significantly for multi-turn sessions.

---

## 5. Policy Matrix (steering.py)

### 5.1 Dynamic Turn Budget

```python
def compute_max_turns(time_remaining, min_time, difficulty) -> int:
    ratio = time_remaining / min_time
    base = {"HARD": 4, "MEDIUM": 3, "EASY": 2}[difficulty]
    if ratio > 3:   return base
    if ratio > 2:   return max(base - 1, 1)
    if ratio > 1.5: return max(base - 2, 1)
    return 1
```

HARD problems get more turns when time allows because design judgment requires depth.
EASY problems cap at 2 turns to stay proportional to the question difficulty.

### 5.2 Intent Selection

Given `time_remaining`, `min_time`, `correctness_passed`, `candidate_depth`, `difficulty`, `turn_count`:

| Condition | Intent | Allowed Formats |
|---|---|---|
| Much time + did well (or HARD difficulty) | `ESCALATE` | CODE¹, MCQ, COMPLEXITY |
| Much time + struggled | `CONSOLIDATE` | TEXT, COMPLEXITY, TRUE_FALSE |
| Little time + did well | `QUICK_PROBE` | MCQ, TRUE_FALSE, COMPLEXITY |
| Little time + struggled | `QUICK_CLOSE` | TRUE_FALSE, TEXT |
| Max turns / STRONG depth / time gate | `CLOSE` | — |

¹ CODE format (IMPLEMENTATION type) is only offered when `time_remaining > 3 × min_time`.

"Much time" = `time_remaining > 2 × min_time`.
HARD bias: HARD difficulty problems treat correctness as "clean" earlier, preferring ESCALATE to
test design judgment rather than staying in CONSOLIDATE.

---

## 6. Interactive Protocol

### 6.1 Acknowledgment

Every LLM response begins with an `acknowledgment` field — 1–3 sentences that:
- Reference something **specific** the candidate did (correctly or incorrectly)
- Name the gap concisely if one exists
- Transition naturally into the follow-up question

This is rendered to the candidate before the follow-up question, making the interview feel like a
real conversation rather than a form submission with a response code.

**Example (code submission):**
> "Good — you correctly identified the indentation issue and fixed the method body. I noticed you
> chose to raise `ValueError` rather than the existing `InvalidOperationException` in this project.
> Let's dig into that decision."
>
> *[follow-up question rendered separately]*

**Example (conversational answer):**
> "That's partially right — you mentioned `@Transactional` but didn't say which isolation level you'd
> use or why. Let me push on that a bit."
>
> *[next question rendered separately]*

### 6.2 Response Shape

```json
{
  "session_id": "...",
  "stage": "FOLLOWUP_CONVERSATIONAL",
  "evaluation": {
    "acknowledgment": "Good solution overall. You correctly checked stock before payment...",
    "correctness": { "rating": 8, "passed": true, "finding": "..." },
    "efficiency":  { "rating": 7, "passed": true, "finding": "..." },
    "follow_up": {
      "intent": "ESCALATE",
      "type": "CONVERSATIONAL",
      "format": "MCQ",
      "question": "What happens when two buyers request the last unit simultaneously?",
      "options": ["A) One succeeds, one fails gracefully", "B) Both succeed, inventory goes negative", "C) Both fail", "D) Depends on the JVM thread scheduler"]
    }
  },
  "next_action": "AWAIT_ANSWER",
  "closed": false,
  "report": null
}
```

Note: `expected_answer_key` and `chosen_area` are **stripped** from the `follow_up` before it
reaches the candidate via `FollowUp.candidate_view()`.

---

## 7. Concept Tracking

### 7.1 Focus Area Sequencing

The service tracks which blueprint focus areas have been probed in `session.probed_areas`. On each
turn, the LLM is told:

- **Already probed** — do not ask about these again
- **Remaining areas** — sorted by `priority` (1 = must-ask, 2 = if-time-allows)

The LLM selects a `chosen_area` from the remaining list and records it in `follow_up.chosen_area`.
The service persists this choice to `session.probed_areas` and, on the next turn when the answer
arrives, scores it into `session.concept_scores[area]`.

### 7.2 Concept Scoring

When a conversational answer is evaluated:
- The **answered** area is identified via `session.active_follow_up.chosen_area`
- `output.answer_rating` → `session.concept_scores[area]`
- `output.finding` → `session.concept_findings[area]`

These flow into the final `EvalReport.concept_dimensions`:

```json
"concept_dimensions": {
  "EXCEPTION_ORDERING": { "rating": 9, "weight": 0, "finding": "Correctly explained stock-first ordering and the buyer-experience implication." },
  "CONCURRENCY":        { "rating": 4, "weight": 0, "finding": "Mentioned @Transactional but could not identify the isolation level needed." }
}
```

`weight: 0` signals these are informational breakdowns, not inputs to `final_score`.

---

## 8. Scoring System (score_profiles.py)

### 8.1 Weight Profiles

| Dimension | EASY | MEDIUM | HARD |
|---|---|---|---|
| correctness | 45% | 40% | 30% |
| efficiency | 20% | 25% | 20% |
| followUp | 20% | 20% | 30% |
| communication / designJudgment | 15% | 15% | 20% |

HARD problems weight `designJudgment` instead of `communication` and reduce `correctness` weight
because design trade-off articulation matters more than getting the basic algorithm right.

### 8.2 Score Formula

```
final_score = round( Σ (rating/10 × 100 × weight) / Σ weights )
```

All ratings are 1–10. Scores are 0–100. The LLM never sees or emits `final_score`.

### 8.3 Report Structure

```python
EvalReport(
    final_score=74,
    weight_profile="MEDIUM",
    dimensions={
        "correctness": DimensionResult(rating=8, weight=40, finding="..."),
        "efficiency":  DimensionResult(rating=7, weight=25, finding="..."),
        "followUp":    DimensionResult(rating=6, weight=20, finding="..."),
        "communication": DimensionResult(rating=6, weight=15, finding="..."),
    },
    concept_dimensions={
        "EXCEPTION_CONTRACT": DimensionResult(rating=9, weight=0, finding="..."),
        "EXTENSIBILITY":      DimensionResult(rating=5, weight=0, finding="..."),
    },
    pace=PaceBlock(turns_used=2, time_consumed_seconds=840, gate_fired=False),
)
```

---

## 9. Blueprint Schema Reference

A blueprint is a JSON document that fully describes one challenge for the evaluation engine.

### 9.1 Top-Level

```jsonc
{
  "problemId": "vending-machine-easy-dispense-product",   // kebab-case, matches DB slug
  "task": { ... },
  "repo": { ... },
  "bugMeta": null,    // non-null for BUG_FIX tasks only
  "evaluation": { ... },
  "followUpContext": { ... }
}
```

### 9.2 `task`

```jsonc
{
  "taskType": "FEATURE_IMPLEMENTATION | BUG_FIX",
  "title": "string",
  "description": "Full problem statement shown to the evaluator",
  "constraints": ["string"],          // explicit pass/fail acceptance criteria
  "difficulty": "EASY | MEDIUM | HARD",
  "targetRole": "SDE-1 | JUNIOR_TO_MID | SDE-2 | ...",
  "language": "Python | Java | ...",
  "framework": "FastAPI | Spring Boot | ...",
  "expectedComplexity": { "time": "O(1)", "space": "O(1)" },
  "concurrencyRequired": false
}
```

### 9.3 `repo`

```jsonc
{
  "targetFile": "path/to/FileToImplement.java",   // primary file for submission
  "relevantFiles": [
    { "path": "src/...", "role": "TARGET | CALLER | DEPENDENCY | SCHEMA | EXCEPTION | STUB | MODEL | REFERENCE" }
  ]
}
```

Files with role `TARGET` are the ones the candidate is expected to change. Other roles provide
context to the LLM prompt. Files are capped at 20KB each and 50KB total before being sent to the LLM.

### 9.4 `bugMeta` (null for feature tasks)

```jsonc
{
  "location": "path/to/file",
  "description": "What is broken and where",
  "correctBehavior": "What it should do",
  "brokenBehavior": "What it does instead",
  "type": "SYNTAX_BUG | LOGIC_BUG | MISSING_IMPORT | ..."
}
```

### 9.5 `evaluation`

```jsonc
{
  "rubric": {
    "correctness": { "9-10": "...", "7-8": "...", "4-6": "...", "1-3": "..." },
    "efficiency":  { "9-10": "...", "7-8": "...", "4-6": "...", "1-3": "..." }
  },
  "senioritySignals": ["string"],   // behaviours that distinguish senior candidates
  "commonMistakes":  ["string"],    // probing points fed into the LLM system prompt
  "passCriteria":    ["string"]     // optional explicit acceptance criteria
}
```

### 9.6 `followUpContext`

```jsonc
{
  "interviewerFocusAreas": [
    {
      "area": "CONCURRENCY",               // unique name; matches concept tracking keys
      "priority": 1,                        // 1 = must-ask first, 2 = if time allows
      "preferredFormat": "MCQ",             // hints the LLM but is not a hard constraint
      "scope": "What to probe and why",
      "probeQuestion": "Suggested starter question",
      "goodAnswerIndicator": "What a strong answer looks like"
    }
  ],
  "expectedApproaches": [
    { "approach": "string", "tradeoff": "string" }
  ],
  "knownEdgeCases": ["string"],
  "scaleUpDimensions": [
    { "dimension": "string", "triggerCondition": "when to use this" }
  ],
  "implementationChallenges": [
    {
      "id": "unique-slug",
      "trigger": "observed condition in candidate's code",
      "instruction": "Exact ask for the candidate — becomes the follow-up question for CODE/IMPLEMENTATION type",
      "targetFile": "path to the file to modify",
      "acceptanceCriteria": "How to verify success",
      "difficulty": "EASY | MEDIUM | HARD"
    }
  ]
}
```

#### Focus Area Priority

| Priority | Meaning |
|---|---|
| 1 | Core concept for this problem — always ask if time allows |
| 2 | Secondary concept — ask only when primary areas are covered and time remains |

#### Preferred Formats per Concept Type

| Concept Type | Recommended Format |
|---|---|
| Exception contract / ordering | MCQ |
| Concurrency / race conditions | MCQ or TRUE_FALSE |
| Complexity analysis | COMPLEXITY |
| Design / extensibility | TEXT |
| Missing implementation | CODE (IMPLEMENTATION type) |
| Quick yes/no knowledge check | TRUE_FALSE |

---

## 10. LLM Prompt Design

### 10.1 Two-Part Message Structure

**System prompt** (stable prefix, cached by OpenAI):
- Interviewer persona
- Task description, constraints, rubric, seniority signals
- All focus areas (with priority, preferred format, probe questions)
- Expected approaches, edge cases, scale-up dimensions, implementation challenges
- Gold-master solution

**User message** (dynamic per turn):
- Candidate's submitted files (or answer text)
- Time remaining
- Already-probed areas (LLM must not repeat these)
- Remaining areas sorted by priority (LLM picks from here)
- Conversation history
- Intent instruction + allowed formats
- JSON schema to fill in

The stable/dynamic split ensures prefix cache hits from turn 2 onward, reducing cost for multi-turn
sessions by 50-70%.

### 10.2 LLM Output Schema — Code Submission

```jsonc
{
  "acknowledgment": "1-3 sentences referencing the candidate's code specifically",
  "correctness": { "rating": 8, "passed": true, "finding": "string" },
  "efficiency":  { "rating": 7, "passed": true, "finding": "string" },
  "follow_up": {
    "intent": "ESCALATE",
    "type": "CONVERSATIONAL",
    "format": "MCQ",
    "question": "The follow-up question shown to the candidate",
    "chosen_area": "CONCURRENCY",          // internal — stripped from candidate view
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "expected_answer_key": "A"             // internal — stripped from candidate view
  },
  "communication_finding": "string or null"
}
```

### 10.3 LLM Output Schema — Conversational Answer

```jsonc
{
  "acknowledgment": "1-3 sentences responding to the candidate's answer",
  "finding": "Evaluation of what the candidate said",
  "candidate_depth": "SHALLOW | ADEQUATE | STRONG",
  "answer_rating": 7,
  "follow_up": {
    "intent": "QUICK_PROBE",
    "type": "CONVERSATIONAL",
    "format": "TRUE_FALSE",
    "question": "The next question",
    "chosen_area": "FLOAT_PRECISION",
    "options": null,
    "expected_answer_key": "False"
  },
  "communication_finding": "string or null"
}
```

### 10.4 Guardrail Validation

After every LLM call:
1. `follow_up.format` must be in `legal_formats` from the policy matrix
2. `follow_up.chosen_area` must be in the blueprint's focus area names (if open areas exist)

If either check fails, a **deterministic templated fallback** replaces the question — the LLM's
area choice and format are discarded, the fallback is constructed from the blueprint's `probeQuestion`
and `scope`, and the session continues normally.

---

## 11. Infrastructure

### 11.1 Session Storage

```
Write path:  Postgres (durable, always) → Redis (warm cache)
Read path:   Redis (fast) → Postgres (fallback, re-warms Redis)
```

Sessions live in `eval_sessions` table (Postgres) with a 90-minute TTL in Redis.

### 11.2 Blueprint Storage

```
Write path:  Postgres (problems.blueprint column) → Redis (1h TTL)
Read path:   Redis → Postgres → local FS (dev fallback, backfills Postgres on first load)
```

### 11.3 LLM Resilience

`tenacity` retry on the LLM client: 3 attempts, exponential backoff (2s–60s) for transient errors
(connection, timeout, rate limit, 5xx). If the model returns malformed JSON, one repair re-ask is
made before giving up. Per-call token cost and cumulative session cost are logged at INFO level.

---

## 12. API Reference

### POST /eval/submit

Called by Java after all automated tests pass.

**Request:**
```json
{
  "problem_id": "vending-machine-easy-dispense-product",
  "session_id": "uuid",
  "submission": {
    "changed_files": { "src/main/java/...Service.java": "<file content>" }
  },
  "gold_master_ref": "s3://bucket/path.zip",
  "time_remaining_seconds": 2700,
  "minimum_time_remaining_seconds": 600
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "stage": "FOLLOWUP_CONVERSATIONAL",
  "evaluation": {
    "acknowledgment": "...",
    "correctness": { "rating": 8, "passed": true, "finding": "..." },
    "efficiency":  { "rating": 7, "passed": true, "finding": "..." },
    "follow_up": { "intent": "ESCALATE", "format": "MCQ", "question": "...", "options": ["A)...", "B)..."] }
  },
  "next_action": "AWAIT_ANSWER",
  "closed": false,
  "report": null
}
```

### POST /eval/answer

Called when the candidate submits a conversational answer. Session must be in `FOLLOWUP_CONVERSATIONAL`.

**Request:**
```json
{
  "problem_id": "vending-machine-easy-dispense-product",
  "session_id": "uuid",
  "answer": "I would use @Transactional with SERIALIZABLE isolation...",
  "time_remaining_seconds": 1800,
  "minimum_time_remaining_seconds": 600
}
```

**Response:** Same shape as `/eval/submit` but `evaluation` has `finding` and `answer_rating` instead
of `correctness`/`efficiency`. When `closed: true`, `report` contains the full `EvalReport`.

### GET /eval/session/{session_id}

Read-only. Returns the raw `SessionState` dict. Used by Java to poll current stage and report.

---

## 13. Adding a New Blueprint

1. Create `platform-eval/blueprint/{problem-id}.json` following the schema in §9.
2. Populate at least **two** `interviewerFocusAreas` with `priority: 1`.
3. Add at least one `implementationChallenge` for MEDIUM/HARD problems.
4. The service will auto-backfill Postgres on first load from local FS (dev) or load from Postgres
   directly (prod, after the DB row is populated by the codegen service).
5. Verify by calling `GET /eval/session/{any-id}` after `/eval/submit` with the new `problem_id`.

---

## 14. Extending the Engine

### Adding a new follow-up format

1. Add the value to `FollowUpFormat` enum in `models/dtos.py`
2. Add it to the appropriate `legal_formats` list in `steering.select_intent_and_formats()`
3. Update the schema description in `interviewer._format_schema_*` to document it

### Adding a new scoring dimension

1. Add the key to the relevant profiles in `config/score_profiles.py`
2. Handle it in `session_manager._compute_report()` (analogous to `followUp` dimension)
3. Update `EvalReport.dimensions` documentation above

### Adding a new difficulty tier

1. Add a profile to `SCORE_PROFILES` in `config/score_profiles.py`
2. Update `compute_max_turns()` in `steering.py` if the tier needs a different turn budget
3. Add test blueprints with the new `difficulty` value
