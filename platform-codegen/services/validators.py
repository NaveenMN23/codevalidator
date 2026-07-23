import json
import re
from typing import Any
from pydantic import BaseModel, field_validator, model_validator
from infrastructure.logger import log

_STRIP_TARGET = re.compile(r"(//|#)\s+@strip-target:")
_STRIP_END = re.compile(r"(//|#)\s+@strip-end\b")

MAX_CORRECTION_ATTEMPTS = 3


class ScenarioMeta(BaseModel):
    tag: str
    title: str
    description: str


class StubLocation(BaseModel):
    file: str
    function_name: str


class SkeletonOutput(BaseModel):
    """Output from Phase 2a skeleton call — codebase with stub functions (throw/raise statements)."""
    files: dict[str, str]
    stub_locations: dict[str, StubLocation]  # keyed by scenario_tag

    @field_validator("files")
    @classmethod
    def files_not_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("files must not be empty")
        
        has_test = False
        for path, content in v.items():
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"File {path!r} has empty content")
            if "test" in path.lower() or path.startswith("src/test/"):
                has_test = True
                
        if not has_test:
            raise ValueError("CRITICAL ERROR: No test files found in the generated skeleton! You MUST include at least one fully implemented test file (e.g. src/test/java/... or test_...py or ...test.ts).")
            
        return v

    @model_validator(mode="after")
    def all_stubs_have_markers(self) -> "SkeletonOutput":
        all_content = "\n".join(self.files.values())
        for tag, stub_loc in self.stub_locations.items():
            # Level 1a: exact stub marker (implement scenarios)
            if f"not implemented: {tag}" in all_content:
                continue
            # Level 1b: debug scenario marker
            if f"DEBUG_SCENARIO: {tag}" in all_content:
                continue
            # Level 2: function present in the declared file with ANY throw/raise body.
            # Accepts skeletons where the LLM used a slightly different stub message;
            # _inject_all_deltas will use a regex fallback to replace the body.
            file_content = self.files.get(stub_loc.file, "")
            has_function = stub_loc.function_name in file_content
            has_throw = any(
                kw in file_content
                for kw in (
                    "throw new Error(",
                    "throw new UnsupportedOperationException(",
                    "raise NotImplementedError(",
                    "raise ",
                )
            )
            if has_function and has_throw:
                log.warning(
                    f"Stub marker 'not implemented: {tag}' not found exactly — "
                    f"accepting because {stub_loc.file!r} contains "
                    f"'{stub_loc.function_name}' with a throw/raise"
                )
                continue
            raise ValueError(
                f"Stub marker 'not implemented: {tag}' not found, and "
                f"function '{stub_loc.function_name}' has no throw/raise "
                f"in {stub_loc.file!r}"
            )
        return self


class SkeletonPatchOutput(BaseModel):
    """Incremental compile-retry patch: only new/corrected files, merged into the
    existing skeleton rather than replacing it."""
    files: dict[str, str] = {}
    remove_files: list[str] = []

    @model_validator(mode="after")
    def at_least_one_change(self) -> "SkeletonPatchOutput":
        if not self.files and not self.remove_files:
            raise ValueError(
                "Provide at least one file to add/fix in `files`, or a path to delete "
                "in `remove_files`."
            )
        for path, content in self.files.items():
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"File {path!r} has empty content")
        return self


class FunctionDeltaOutput(BaseModel):
    """Output from Phase 2b function delta call — one function body + its hidden test.

    For debug scenarios, `bug_code` holds the broken implementation that goes into the
    student scaffold (the skeleton already has it, but this field makes it explicit).

    For `check_mode: non_deterministic` scenarios, `rubric` holds the LLM-judge grading
    criteria produced by `judge_function_{lang}` in place of `test_hidden` — the candidate's
    submission is scored against it by an LLM judge rather than exact-match assertions.
    """
    function_body: str
    test_hidden: str = ""
    test_visible: str
    bug_code: str | None = None
    imports: list[str] = []
    fields: list[str] = []
    rubric: list[dict] | None = None

    @field_validator("function_body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("function_body must not be empty")
        return v

    @field_validator("test_visible")
    @classmethod
    def visible_test_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("test_visible must not be empty")
        return v

    @model_validator(mode="after")
    def test_hidden_or_rubric_present(self) -> "FunctionDeltaOutput":
        # Judge-mode (check_mode: non_deterministic) deltas carry `rubric` instead of a
        # hidden test suite — `test_hidden` is legitimately empty in that case. Every
        # other delta must still have a non-empty test_hidden, as before.
        if not self.rubric and (not self.test_hidden or not self.test_hidden.strip()):
            raise ValueError("test_hidden must not be empty unless rubric is provided")
        return self


class JudgeQAOutput(BaseModel):
    """Output from Phase 4 judge_scenario_qa call — QA verdict on a single generated scenario."""
    assessed_tier: str
    difficulty_match: bool
    time_estimate_minutes: int
    time_in_range: bool
    topic_match: bool
    tests_valid: bool
    test_issues: list[str] = []
    overall_pass: bool
    findings: str


class SingleTierOutput(BaseModel):
    """Output from one Phase 2 LLM call — files + 3 tests + 3 scenario metadata entries."""
    files: dict[str, str]
    test_hidden: dict[str, str]   # {scenario_tag: complete test file content}
    scenarios: list[ScenarioMeta] # 3 items, one per scenario

    @field_validator("files")
    @classmethod
    def files_not_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("files must not be empty")
        for path, content in v.items():
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"File {path!r} has empty content")
        return v

    @field_validator("test_hidden")
    @classmethod
    def test_hidden_not_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("test_hidden must not be empty")
        for tag, content in v.items():
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"test_hidden[{tag!r}] has empty content")
        return v

    @field_validator("scenarios")
    @classmethod
    def scenarios_count(cls, v: list) -> list:
        if len(v) != 3:
            raise ValueError(f"scenarios must contain exactly 3 items, got {len(v)}")
        return v

    @model_validator(mode="after")
    def strip_markers_balanced(self) -> "SingleTierOutput":
        for path, content in self.files.items():
            n_open = len(_STRIP_TARGET.findall(content))
            n_close = len(_STRIP_END.findall(content))
            if n_open != n_close:
                raise ValueError(
                    f"Unbalanced @strip markers in {path!r}: "
                    f"{n_open} @strip-target vs {n_close} @strip-end"
                )
        return self

    @model_validator(mode="after")
    def all_scenario_tags_in_strip(self) -> "SingleTierOutput":
        all_content = "\n".join(self.files.values())
        for scenario in self.scenarios:
            if f"@strip-target: {scenario.tag}" not in all_content:
                raise ValueError(
                    f"scenario tag {scenario.tag!r} not found in any @strip-target annotation"
                )
        return self

    @model_validator(mode="after")
    def test_hidden_covers_all_scenarios(self) -> "SingleTierOutput":
        expected = {s.tag for s in self.scenarios}
        missing = expected - set(self.test_hidden.keys())
        if missing:
            raise ValueError(f"test_hidden missing entries for scenarios: {missing}")
        return self


class GoldMasterOutput(BaseModel):
    """Legacy single-scenario output — kept for backward compatibility with tests."""
    files: dict[str, str]
    test_hidden: dict[str, str]
    manifest: dict[str, Any]

    @field_validator("files")
    @classmethod
    def files_not_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("files must not be empty")
        for path, content in v.items():
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"File {path!r} has empty content")
        return v

    @field_validator("test_hidden")
    @classmethod
    def test_files_not_empty(cls, v: dict) -> dict:
        for tag, content in v.items():
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"test_hidden[{tag!r}] has empty content")
        return v

    @model_validator(mode="after")
    def test_hidden_covers_all_scenarios(self) -> "GoldMasterOutput":
        scenarios = set(self.manifest.get("scenarios", {}).keys())
        missing = scenarios - set(self.test_hidden.keys())
        if missing:
            raise ValueError(f"test_hidden is missing entries for scenarios: {missing}")
        return self

    @model_validator(mode="after")
    def strip_markers_balanced(self) -> "GoldMasterOutput":
        for path, content in self.files.items():
            n_open = len(_STRIP_TARGET.findall(content))
            n_close = len(_STRIP_END.findall(content))
            if n_open != n_close:
                raise ValueError(
                    f"Unbalanced @strip markers in {path!r}: "
                    f"{n_open} @strip-target vs {n_close} @strip-end"
                )
        return self


class DesignOutput(BaseModel):
    challenge: dict[str, Any]
    entities: list[dict]
    difficulty_tiers: dict[str, Any]

    @field_validator("difficulty_tiers")
    @classmethod
    def has_required_tiers(cls, v: dict) -> dict:
        if not v:
            raise ValueError("difficulty_tiers must not be empty")
        for tier, tier_data in v.items():
            if "scenarios" not in tier_data:
                raise ValueError(f"difficulty_tiers[{tier!r}] missing 'scenarios' array")
            if not tier_data["scenarios"]:
                raise ValueError(f"difficulty_tiers[{tier!r}].scenarios must not be empty")
            for i, scenario in enumerate(tier_data["scenarios"]):
                for required in ("scenario_tag", "title", "description"):
                    if required not in scenario:
                        raise ValueError(
                            f"difficulty_tiers[{tier!r}].scenarios[{i}] missing field: {required!r}"
                        )
        return v


def validate_with_correction(
    raw: str,
    model_cls: type[BaseModel],
    llm_call,
    system_prompt: str,
    user_message: str,
    label: str = "",
) -> BaseModel:
    """Parse + validate LLM JSON output; on failure retry with a correction prompt (max 2 times)."""
    attempt = 0
    last_error = None
    current_raw = raw

    while attempt <= MAX_CORRECTION_ATTEMPTS:
        try:
            data = json.loads(current_raw)
            validated = model_cls.model_validate(data)
            if attempt > 0:
                log.info(f"[{label}] Validation passed on correction attempt {attempt}")
            return validated
        except Exception as e:
            last_error = e
            attempt += 1
            if attempt > MAX_CORRECTION_ATTEMPTS:
                break
            log.warning(f"[{label}] Validation failed (attempt {attempt}): {e}. Sending correction prompt.")
            correction_user = (
                f"{user_message}\n\n"
                f"Your previous response was invalid:\n{e}\n\n"
                f"Return the corrected JSON only, matching the required schema exactly."
            )
            current_raw = llm_call(system_prompt, correction_user)

    raise ValueError(
        f"[{label}] Output validation failed after {MAX_CORRECTION_ATTEMPTS} correction attempts: {last_error}"
    )
