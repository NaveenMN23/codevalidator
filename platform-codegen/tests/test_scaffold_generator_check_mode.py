"""Tests for LLM-judged non-deterministic checks (Feature 1) and the topic/QA
manifest fields (Feature 2) — see LLM_JUDGE_IMPLEMENTATION_PLAN.md at repo root.

These exercise the pure, non-LLM parts of the pipeline: manifest assembly and
the Pydantic schemas the LLM outputs are validated against. Generation itself
(Phase 1-4 LLM calls) has no existing test coverage of that kind in this repo
(no mocking framework for llm_client is set up), so this suite matches that
established convention rather than introducing a new one.
"""
import pytest
from pydantic import ValidationError
from services.scaffold_generator import (
    scaffold_generator,
    _TOPICS,
    _REQUIRED_TEST_CATEGORIES,
    _select_delta_prompt_name,
)
from services.validators import DesignOutput, FunctionDeltaOutput, JudgeQAOutput


class TestSelectDeltaPromptName:
    def test_deterministic_implement_uses_implement_prompt(self):
        assert _select_delta_prompt_name("java", "implement", "deterministic") == "implement_function_java"

    def test_deterministic_debug_uses_debug_prompt(self):
        assert _select_delta_prompt_name("node", "debug", "deterministic") == "debug_function_node"

    def test_non_deterministic_implement_uses_judge_prompt(self):
        assert _select_delta_prompt_name("python", "implement", "non_deterministic") == "judge_function_python"

    def test_non_deterministic_debug_still_uses_judge_prompt(self):
        # check_mode wins over scenario_type — a debug scenario can still be judge-graded
        assert _select_delta_prompt_name("java", "debug", "non_deterministic") == "judge_function_java"


def _design_with_scenario(scenario_extra: dict) -> DesignOutput:
    base_scenario = {
        "scenario_tag": "easy-cancel-booking",
        "type": "implement",
        "title": "Cancel a Booking",
        "description": "desc",
        "strip_description": "strip",
        "bug_description": "",
    }
    base_scenario.update(scenario_extra)
    return DesignOutput(
        challenge={"name": "test-challenge", "domain": "ticketing"},
        entities=[{"name": "booking", "fields": ["id"]}],
        difficulty_tiers={"easy": {"scenarios": [base_scenario]}},
    )


def test_manifest_defaults_check_mode_to_deterministic_when_absent():
    design = _design_with_scenario({})
    manifest = scaffold_generator._build_manifest("test-challenge", "java", design, ["easy"])
    entry = manifest["scenarios"]["easy-cancel-booking"]
    assert entry["check_mode"] == "deterministic"
    assert "rubric" not in entry


def test_manifest_carries_rubric_for_non_deterministic_scenario():
    design = _design_with_scenario({"check_mode": "non_deterministic", "topic": "resilience"})
    delta = FunctionDeltaOutput(
        function_body="return null;",
        test_visible="// smoke test",
        rubric=[{"criterion": "Handles the described edge case", "weight": 3}],
    )
    tier_deltas = {"easy": {"easy-cancel-booking": delta}}
    manifest = scaffold_generator._build_manifest(
        "test-challenge", "java", design, ["easy"], tier_deltas,
    )
    entry = manifest["scenarios"]["easy-cancel-booking"]
    assert entry["check_mode"] == "non_deterministic"
    assert entry["topic"] == "resilience"
    assert entry["rubric"] == [{"criterion": "Handles the described edge case", "weight": 3}]


def test_manifest_rubric_is_none_when_delta_missing_for_non_deterministic_scenario():
    design = _design_with_scenario({"check_mode": "non_deterministic"})
    manifest = scaffold_generator._build_manifest("test-challenge", "java", design, ["easy"])
    entry = manifest["scenarios"]["easy-cancel-booking"]
    assert entry["rubric"] is None


def test_manifest_carries_qa_report_when_provided():
    design = _design_with_scenario({"topic": "concurrency"})
    qa_report = {
        "assessed_tier": "easy", "difficulty_match": True, "time_estimate_minutes": 45,
        "time_in_range": True, "topic_match": True, "tests_valid": True,
        "test_issues": [], "overall_pass": True, "findings": "looks fine",
    }
    tier_qa_reports = {"easy": {"easy-cancel-booking": qa_report}}
    manifest = scaffold_generator._build_manifest(
        "test-challenge", "java", design, ["easy"], None, tier_qa_reports,
    )
    entry = manifest["scenarios"]["easy-cancel-booking"]
    assert entry["topic"] == "concurrency"
    assert entry["qa_report"] == qa_report


def test_manifest_qa_report_is_none_when_not_provided():
    design = _design_with_scenario({})
    manifest = scaffold_generator._build_manifest("test-challenge", "java", design, ["easy"])
    entry = manifest["scenarios"]["easy-cancel-booking"]
    assert entry["qa_report"] is None
    assert entry["topic"] is None


class TestFunctionDeltaOutputSchema:
    def test_accepts_populated_rubric_with_empty_test_hidden(self):
        delta = FunctionDeltaOutput(
            function_body="return null;",
            test_visible="// smoke test",
            rubric=[{"criterion": "x", "weight": 1}],
        )
        assert delta.test_hidden == ""
        assert delta.rubric == [{"criterion": "x", "weight": 1}]

    def test_rejects_empty_test_hidden_without_rubric(self):
        with pytest.raises(ValidationError, match="test_hidden must not be empty unless rubric is provided"):
            FunctionDeltaOutput(function_body="return null;", test_visible="// smoke test")

    def test_deterministic_delta_still_requires_test_hidden(self):
        delta = FunctionDeltaOutput(
            function_body="return null;",
            test_hidden="// hidden test",
            test_visible="// smoke test",
        )
        assert delta.rubric is None
        assert delta.test_hidden == "// hidden test"

    def test_rejects_empty_function_body(self):
        with pytest.raises(ValidationError, match="function_body must not be empty"):
            FunctionDeltaOutput(function_body="  ", test_hidden="t", test_visible="v")

    def test_rejects_empty_test_visible(self):
        with pytest.raises(ValidationError, match="test_visible must not be empty"):
            FunctionDeltaOutput(function_body="return null;", test_hidden="t", test_visible="  ")


class TestJudgeQAOutputSchema:
    def test_parses_a_passing_verdict(self):
        verdict = JudgeQAOutput(
            assessed_tier="easy", difficulty_match=True, time_estimate_minutes=45,
            time_in_range=True, topic_match=True, tests_valid=True,
            test_issues=[], overall_pass=True, findings="fine",
        )
        assert verdict.overall_pass is True
        assert verdict.test_issues == []

    def test_parses_a_failing_verdict_with_issues(self):
        verdict = JudgeQAOutput(
            assessed_tier="hard", difficulty_match=False, time_estimate_minutes=90,
            time_in_range=False, topic_match=True, tests_valid=False,
            test_issues=["testFoo asserts unrelated behavior"],
            overall_pass=False, findings="too hard and off-topic tests",
        )
        assert verdict.overall_pass is False
        assert verdict.test_issues == ["testFoo asserts unrelated behavior"]

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            JudgeQAOutput(assessed_tier="easy", difficulty_match=True)


def test_topic_taxonomy_is_a_fixed_nonempty_list_of_unique_lowercase_slugs():
    assert len(_TOPICS) > 0
    assert len(_TOPICS) == len(set(_TOPICS))
    for topic in _TOPICS:
        assert topic == topic.lower()
        assert " " not in topic


def test_required_test_categories_grow_with_tier():
    easy = set(_REQUIRED_TEST_CATEGORIES["easy"])
    medium = set(_REQUIRED_TEST_CATEGORIES["medium"])
    hard = set(_REQUIRED_TEST_CATEGORIES["hard"])
    assert easy.issubset(medium)
    assert medium.issubset(hard)
    assert len(hard) > len(easy)
