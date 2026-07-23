# LLM-Judged Non-Deterministic Checks in platform-codegen

## Context

Investigating the docker logs revealed the trigger issue — a `LoanServiceTest` H2 "Table LOAN not found" failure — was a one-off from an earlier, unrelated generation job and is **not currently reproducing** (confirmed against the latest `codegen` container logs; the most recent job completed successfully). It is out of scope for this plan.

The real gap, confirmed by direct code inspection: **platform-codegen has no concept of "deterministic" vs "non-deterministic" checks at all.** Every generated scenario gets the exact same kind of hidden test — a JUnit 5 file with hardcoded minimum assertion counts (`platform-codegen/prompts/implement_function_java.mdx:52-58`) — regardless of whether the scenario's correct output can legitimately vary. There's no schema field to request otherwise: `GoldenRepoRequest` (`platform-codegen/api/routes.py:10-11`) uses `ConfigDict(extra="forbid")`, so any unrecognized field is rejected outright rather than silently ignored, and a repo-wide grep for determinism-related field names returns nothing.

Decision (confirmed with user): non-deterministic checks mean **LLM-judged rubric grading** instead of exact-match assertions — for outputs that legitimately vary (free text, formatting, timing, etc.). The rubric output should reuse platform-eval's existing structured-judging shape (`CorrectnessRating` / `EfficiencyRating` in `platform-eval/models/dtos.py:131-140`: `rating (1-10)`, `passed: bool`, `finding: str`) rather than invent a new format, since `session_manager.py:300` already treats "deterministic" as *the scoring math on top of LLM ratings*, not the ratings themselves — this is the same mental model, just applied one level earlier (grading a check instead of a whole submission).

This plan covers the **codegen side only**: generating and persisting rubric-based checks in the right shape. Wiring platform-eval to actually grade against a stored rubric is a natural next step but out of scope here.

## How the request actually reaches codegen

The real generation pipeline is async over RabbitMQ, not the sync `/admin/generate-golden-repo` REST route. `platform-codegen/infrastructure/consumer.py` handles `DESIGN_PREVIEW` and `FULL_GENERATE` jobs, pulling loosely-typed fields straight off the message body (e.g. `body.get("debugScenariosPerTier", 1)`) and passing them into `scaffold_generator.generate_design_only(...)` / `.generate(...)`. `debug_scenarios_per_tier` is the closest existing analog to what's needed here — same shape of feature (a per-tier count that changes how many scenarios get a different treatment), so the new field should follow that exact pattern end-to-end.

## Implementation

**1. Thread a new per-tier count through the job/generation entry points**
- `infrastructure/consumer.py:18,37`: add `non_deterministic_scenarios_per_tier=body.get("nonDeterministicScenariosPerTier", 0)` alongside the existing `debug_scenarios_per_tier` reads, in both `_handle_design_preview` and `_handle_full_generate`.
- `services/scaffold_generator.py`: add `non_deterministic_scenarios_per_tier: int = 0` as a parameter to both `generate_design_only(...)` (~line 1236-1244) and `generate(...)` (~line 1269-1278), defaulting to 0 so existing callers/behavior are unchanged.

**2. Design prompt — teach Phase 1 to assign `check_mode` per scenario**
- `prompts/design_challenge.mdx`: add a `<non_deterministic_scenarios_per_tier>` input variable next to `<debug_scenarios_per_tier>` (documented in the "You will receive" list, ~line 14).
- Add `"check_mode": "deterministic" | "non_deterministic"` to the scenario JSON schema block (~lines 62-85), defaulting every example to `"deterministic"`.
- Add a distribution rule next to the existing debug-count rule (~lines 163-166): generate exactly the requested count of `non_deterministic` scenarios per tier, independent of the `implement`/`debug` axis (a scenario can be `implement`+`non_deterministic`, `debug`+`deterministic`, etc. — these are orthogonal axes). If the count is 0, all scenarios are `deterministic` (current behavior, unchanged).
- Both call sites building `design_user_msg` (`generate_design_only` ~line 1253-1260, and `generate` ~lines 1323-1329, plus the cache-key fingerprint dict ~line 1305-1314) need the new `<non_deterministic_scenarios_per_tier>` tag added and included in the cache key so a design generated with a different count isn't reused incorrectly.
- `services/validators.py` `DesignOutput` (~line 249-264): `difficulty_tiers` is already `dict[str, Any]` with loose per-scenario validation — no schema class change needed, `check_mode` just rides along as an extra dict key like `type` already does.

**3. Phase 2b — branch on `check_mode`, not just `type`**
- `services/scaffold_generator.py:1597-1601` currently picks `debug_function_{lang}` vs `implement_function_{lang}` based on `scenario.get("type")`. Extend this: when `scenario.get("check_mode") == "non_deterministic"`, use a new prompt `judge_function_{lang}` instead (orthogonal to the implement/debug choice — a debug scenario can still be judge-graded). Simplest correct approach: three prompt variants aren't needed if the judge prompt itself is generic enough for implement or debug intent — pass `<scenario_type>` into it so it adapts its instructions, matching how `implement_function_java.mdx` already receives `<scenario_tag>`/`<strip_description>`/`<bug_description>`.
- New prompt file `prompts/judge_function_java.mdx` (mirror the structure of `implement_function_java.mdx`, same input variables), replacing the "Hidden Test Requirements" section (lines 41-79 in the existing file) with rubric-generation instructions: 3-6 rubric criteria, each with a `criterion` description and `weight`, to be graded by an LLM judge producing `rating (1-10)/passed/finding` per criterion — mirroring `CorrectnessRating`/`EfficiencyRating` in `platform-eval/models/dtos.py:131-140`. Output schema replaces `test_hidden`/`test_visible` with a `rubric: [{ "criterion": str, "weight": int }]` array; still require a minimal `test_visible` smoke test (compiles + runs, no assertions on subjective content) so the existing compile/test-validation pipeline (`compile_validator.validate_compilation`) still has something concrete to check at generation time.
- Only build `judge_function_java.mdx` for the languages actually in use today (repo has `implement_function_java.mdx`/`debug_function_java.mdx` — check for `_node`/`_python` siblings and mirror whichever exist; don't invent variants for unsupported languages).

**4. Extend `FunctionDeltaOutput` to carry the rubric**
- `services/validators.py:105-116`: add `rubric: list[dict] | None = None` to `FunctionDeltaOutput`, alongside existing `test_hidden`/`test_visible`/`bug_code`. Leave `test_hidden`/`test_visible` as-is (no validator requires non-empty content on those today, so a judge-mode delta can carry an empty/minimal `test_hidden`).

**5. Manifest — don't let `check_mode`/`rubric` get silently dropped**
- `services/scaffold_generator.py:_build_manifest` (~line 1910-1931): add `"check_mode": scenario.get("check_mode", "deterministic")` to each scenario's manifest entry (same place `"type"` is already added, line 1925). Since `_build_manifest` runs after `tier_deltas` is fully populated (called at line 1699, after the Phase 2b loop), pass `tier_deltas` through as a new parameter so that when `check_mode == "non_deterministic"`, the manifest entry also gets `"rubric": tier_deltas[tier][tag].rubric` — this is the field platform-eval (or any future consumer) would read to grade against later.

**6. Tests**
- Per `CLAUDE.md`, Python tests live in `platform-codegen/tests/` with relative imports. Add/extend tests covering:
  - `design_challenge` prompt output validation: a design response with `non_deterministic_scenarios_per_tier > 0` produces the right count of `check_mode: non_deterministic` scenarios per tier (mock the LLM call, assert on `DesignOutput` parsing).
  - Phase 2b branch selection: given a scenario dict with `check_mode: non_deterministic`, `scaffold_generator` loads the `judge_function_{lang}` prompt, not `implement_function_{lang}`/`debug_function_{lang}`.
  - `FunctionDeltaOutput` accepts a populated `rubric` field and round-trips through `_build_manifest`.
  - Consumer: `body.get("nonDeterministicScenariosPerTier", 0)` defaults to 0 and is forwarded correctly for both `DESIGN_PREVIEW` and `FULL_GENERATE`.

## Verification (Feature 1)

1. Run the existing `platform-codegen/tests/` suite (`pytest`, per `CLAUDE.md`) to confirm no regression to current deterministic-only behavior when the new field is omitted/0.
2. `docker compose up --build codegen` and trigger a `FULL_GENERATE` job with `nonDeterministicScenariosPerTier: 1` for one tier — confirm in the codegen logs that Phase 1 design output includes a scenario with `check_mode: non_deterministic`, Phase 2b logs show the `judge_function_{lang}` prompt was used for that scenario, and the resulting manifest.json (uploaded gold master) contains the `rubric` array for that scenario tag.
3. Confirm a request with the field omitted (or 0) behaves identically to today — all scenarios `deterministic`, existing JUnit hidden-test generation path unchanged.

---

# Feature 2: LLM-Judge QA Gate on Generated Scenarios

## Context

Beyond grading how a *candidate* is judged (Feature 1), the user wants codegen to use an LLM judge to QA the *generated challenge itself*, right after generation, checking four things per scenario:
1. Difficulty calibration — does the judge, solving the problem cold, agree with the assigned tier?
2. Time calibration — is the judge's estimated solve time between 40 and 60 minutes?
3. Topic correctness — codegen must first tag each scenario with a topic/category (e.g. `concurrency`, `caching`, `pagination`) — a concept that doesn't exist anywhere in the schema today (confirmed via grep — no `topic`/`category` field exists) — and the judge must verify the tag actually matches what the scenario exercises.
4. Test-case correctness and coverage — no incorrect/unrelated assertions in visible or hidden tests, and hidden tests must exercise a full range of input types (edge cases, boundary values, invalid input, etc.).

Decisions confirmed with user:
- **On judge failure: auto-retry/self-heal**, feeding the judge's findings back into a regeneration call for that scenario, capped, then hard-fail — mirroring the existing self-heal retry patterns already in this file (Phase 2b compile-retry loop, `scaffold_generator.py:1629-1696`, and the gold-master compile/test retry loop, `scaffold_generator.py:1725-1817`).
- **Topic taxonomy: fixed enum**, chosen by Phase 1 design from a closed list, verified by the judge against the same list (not freeform).

This is a genuinely new phase (Phase 4) — no post-generation QA/judging step exists today; Phase 3 is blueprint generation for platform-eval, unrelated to QA.

**Cost/latency note to flag explicitly:** this adds one extra LLM call per scenario (up to 3 with retries), on top of the existing Phase 1/2a/2b/3 calls. Worth confirming this tradeoff is acceptable before implementing, since it materially increases generation cost and latency per job.

## Implementation

**1. Fixed topic taxonomy**
- Define a closed list (e.g. in a new `services/taxonomy.py` or alongside `_TIERS`/`_SUPPORTED_LANGUAGES` in `scaffold_generator.py`): `_TOPICS = {"concurrency", "caching", "pagination", "auth-authz", "data-modeling", "idempotency", "rate-limiting", "consistency", "resilience", "search-filtering", ...}`. Treat this list as a starting point — user should review/edit before implementation.
- Pass it into the design prompt as a new `<allowed_topics>` input variable (same pattern as `<tiers>`/`<languages>` today).

**2. Design prompt — assign `topic` per scenario**
- `prompts/design_challenge.mdx`: add `"topic": "<one of allowed_topics>"` to the scenario JSON schema (next to the `check_mode` addition from Feature 1), with a rule that it must be chosen from `<allowed_topics>` — analogous to how `type`/`check_mode` rules are written.
- Threading: same call sites as Feature 1 (`generate_design_only`, `generate`, both `design_user_msg` builds, and the Phase-1 cache-key fingerprint) need the `<allowed_topics>` tag added.
- No `DesignOutput` schema class change needed — `topic` rides along as a loose dict key like `type`/`check_mode`.

**3. New Phase 4 — per-scenario judge QA pass**
- New prompt `prompts/judge_scenario_qa.mdx`, `model: gpt-4o` — same tier as every other generation prompt in this repo (confirmed all existing `.mdx` prompts use `gpt-4o` uniformly; `gpt-4o-mini` was considered but rejected for this judge: task 1 requires the judge to independently re-solve the problem, and task 4 requires catching subtle test-correctness bugs — both need comparable capability to the generator, not a lighter model).
- **Self-preference bias mitigation for task 4 (test-case review):** since the judge and the generator share the same model family, it risks rubber-stamping its own generated tests. Task 1 (difficulty) is naturally protected — the judge solves the problem cold, without seeing the gold master, so it's producing an independent artifact to compare, not reviewing its own output. Task 4 is not naturally protected, so the prompt must use **adversarial framing**: instruct the judge to actively hunt for concrete rule violations against the existing test-category checklist (`implement_function_{lang}.mdx` "Required test categories" table) and emit one itemized `test_issues[]` entry per violation found — never ask a holistic "does this look fine?" question, which is what invites rubber-stamping. `tests_valid` is derived from whether `test_issues` is empty, not asked for directly.
- Inputs: scenario description, `strip_description`/`bug_description`, assigned `tier`, assigned `topic`, the gold-master function implementation, and its hidden+visible test files (or, for `check_mode: non_deterministic` scenarios from Feature 1, the generated `rubric` instead of test files).
- Judge tasks and output schema:
  ```json
  {
    "assessed_tier": "easy|medium|hard",
    "difficulty_match": true,
    "time_estimate_minutes": 45,
    "time_in_range": true,
    "topic_match": true,
    "tests_valid": true,
    "test_issues": [],
    "overall_pass": true,
    "findings": "..."
  }
  ```
- For `check_mode: deterministic` scenarios: `tests_valid`/`test_issues` evaluate the JUnit hidden+visible tests — no assertions unrelated to the described behavior, no dead/TODO code, and coverage of the required test categories already defined in `implement_function_{lang}.mdx` (happy path, not-found, forbidden, validation, boundary, state consistency, idempotency, etc. — the judge audits compliance with requirements that already exist, it doesn't invent new ones).
- For `check_mode: non_deterministic` scenarios (Feature 1): `tests_valid`/`test_issues` instead evaluate rubric quality — criteria are specific and map to the described behavior, weights are sensible — since there are no JUnit assertions to check.
- `time_in_range` uses the 40-60 minute window specified by the user (note: this differs from the "calibrated to exactly 60 minutes" language already in `design_challenge.mdx:20` — the judge's gate should use the 40-60 range as the actual pass/fail check, since that's the explicit instruction).

**4. Wire into `generate()` with the existing self-heal pattern**
- Run once per scenario, right after that scenario's delta passes the existing Phase 2b compile-retry loop (`scaffold_generator.py:1629-1696`) — catches issues while still cheap, before gold-master merge/upload.
- On `overall_pass == False`: build a corrective-feedback retry using the same shape as the existing hint-retry pattern (`scaffold_generator.py:1680-1696`) — feed `findings`/`test_issues` back into a fresh call to whichever prompt produced the delta (`implement_function_{lang}`, `debug_function_{lang}`, or `judge_function_{lang}` from Feature 1), re-run the QA judge on the new output, capped at 2 extra attempts (mirroring `_MAX_GOLD_MASTER_RETRIES = 2` at line 1725). If still failing after the cap, hard-fail that scenario/job with a clear error, consistent with how gold-master compile/test failures already hard-fail today.

**5. Manifest**
- `_build_manifest` (`scaffold_generator.py:1910-1931`): add `"topic"` per scenario (same place as Feature 1's `"check_mode"` addition) and `"qa_report"` (the final passing judge output) so the QA outcome is visible downstream rather than discarded after the retry loop finishes.

**6. Tests**
- `platform-codegen/tests/`, relative imports per `CLAUDE.md`. Cover: judge prompt output parsing, topic-enum enforcement in design output, and the retry-then-hard-fail state machine via mocked judge responses (fail twice → succeeds on 3rd → scenario completes; fails all attempts → job raises with a clear message).

## Verification (Feature 2)

1. `pytest` in `platform-codegen/tests/` — retry/hard-fail logic and topic-enum validation covered by mocks, no live LLM calls needed for these.
2. `docker compose up --build codegen`, trigger a `FULL_GENERATE` job, inspect logs for `judge_scenario_qa` calls per scenario and confirm `qa_report`/`topic` appear in the uploaded manifest.json.
3. Force a judge failure (e.g. temporarily stub the judge prompt to always return `overall_pass: false`) and confirm the retry-then-hard-fail path actually triggers and surfaces a clear error, rather than silently succeeding.
