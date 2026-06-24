import pytest
from pydantic import ValidationError
from models.dtos import (
    FollowUp, FollowUpIntent, FollowUpType, FollowUpFormat,
    CodeEvalOutput, ConversationalEvalOutput, SessionState, Stage,
    CorrectnessRating, EfficiencyRating, CandidateDepth,
)


def _make_follow_up(**kwargs):
    defaults = dict(
        intent=FollowUpIntent.ESCALATE,
        type=FollowUpType.CONVERSATIONAL,
        format=FollowUpFormat.MCQ,
        question="Which of the following is O(1)?",
        options=["A) HashMap lookup", "B) Linear scan"],
        expected_answer_key="A",
    )
    defaults.update(kwargs)
    return FollowUp(**defaults)


def test_follow_up_candidate_view_excludes_answer_key():
    fu = _make_follow_up()
    view = fu.candidate_view()
    assert "expected_answer_key" not in view
    assert view["question"] == fu.question
    assert view["options"] == fu.options


def test_follow_up_round_trip():
    fu = _make_follow_up()
    dumped = fu.model_dump()
    # expected_answer_key IS present in full dump (server side)
    assert dumped["expected_answer_key"] == "A"
    restored = FollowUp.model_validate(dumped)
    assert restored.intent == fu.intent


def test_code_eval_output_validates():
    data = {
        "correctness": {"rating": 8, "passed": True, "finding": "Good"},
        "efficiency": {"rating": 6, "passed": True, "finding": "Adequate"},
        "follow_up": {
            "intent": "ESCALATE",
            "type": "CONVERSATIONAL",
            "format": "MCQ",
            "question": "Which is better?",
            "options": ["A) X", "B) Y"],
        },
    }
    out = CodeEvalOutput.model_validate(data)
    assert out.correctness.rating == 8
    assert out.follow_up.format == FollowUpFormat.MCQ


def test_code_eval_output_tolerates_missing_optional():
    data = {
        "correctness": {"rating": 5, "passed": False, "finding": "Bug"},
        "efficiency": {"rating": 5, "passed": False, "finding": "Slow"},
    }
    out = CodeEvalOutput.model_validate(data)
    assert out.follow_up is None
    assert out.communication_finding is None


def test_session_state_defaults():
    s = SessionState(session_id="abc", problem_id="vending-machine-easy")
    assert s.stage == Stage.INITIAL_SUBMISSION
    assert s.closed is False
    assert s.turn_count == 0
    assert s.answer_ratings == []


def test_conversational_eval_validates():
    data = {
        "finding": "Candidate showed shallow understanding.",
        "candidate_depth": "SHALLOW",
        "answer_rating": 4,
    }
    out = ConversationalEvalOutput.model_validate(data)
    assert out.candidate_depth == CandidateDepth.SHALLOW
    assert out.follow_up is None
