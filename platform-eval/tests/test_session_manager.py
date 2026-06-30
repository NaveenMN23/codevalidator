"""
Unit tests for session_manager: gate, matrix invocation, score math, close logic.
No LLM calls — all LLM output is constructed manually.
"""
import pytest
from unittest.mock import MagicMock, patch
from models.dtos import (
    SessionState, Stage, NextAction, CandidateDepth, FollowUpIntent,
    CodeEvalOutput, ConversationalEvalOutput, CorrectnessRating, EfficiencyRating,
    FollowUp, FollowUpType, FollowUpFormat,
)
from services.session_manager import SessionManager

_BLUEPRINT = {
    "task": {"description": "Test task", "difficulty": "EASY"},
    "rubric": "Rate it.",
    "followUpContext": {"interviewerFocusAreas": []},
}


def _make_manager(session: SessionState):
    mgr = SessionManager()
    # Patch the store so no DB/Redis calls happen
    with patch("services.session_manager.session_store") as mock_store:
        mock_store.load.return_value = None
        mock_store.save.return_value = None
        yield mgr, mock_store


@pytest.fixture
def manager():
    return SessionManager()


@pytest.fixture
def fresh_session():
    return SessionState(session_id="test-123", problem_id="vending-machine-easy")


def _follow_up(intent=FollowUpIntent.ESCALATE, fmt=FollowUpFormat.MCQ):
    return FollowUp(
        intent=intent,
        type=FollowUpType.CONVERSATIONAL,
        format=fmt,
        question="Which is O(1)?",
        options=["A) X", "B) Y"],
        expected_answer_key="A",
    )


def test_gate_fires_at_min_time(manager):
    assert manager.is_gate_fired(600, 600) is True


def test_gate_does_not_fire_above_min(manager):
    assert manager.is_gate_fired(601, 600) is False


def test_reconcile_code_submission_sets_follow_up(manager, fresh_session):
    output = CodeEvalOutput(
        correctness=CorrectnessRating(rating=8, passed=True, finding="Good"),
        efficiency=EfficiencyRating(rating=7, passed=True, finding="OK"),
        follow_up=_follow_up(),
    )
    with patch("services.session_manager.session_store"):
        session, action = manager.reconcile_code_submission(
            session=fresh_session,
            output=output,
            intent=FollowUpIntent.ESCALATE,
            force_close=False,
            blueprint=_BLUEPRINT,
            time_remaining=2000,
            min_time=600,
        )
    assert action == NextAction.AWAIT_ANSWER
    assert session.stage == Stage.FOLLOWUP_CONVERSATIONAL
    assert session.active_follow_up is not None
    assert session.turn_count == 1
    assert session.closed is False


def test_reconcile_closes_on_force_close(manager, fresh_session):
    output = CodeEvalOutput(
        correctness=CorrectnessRating(rating=6, passed=True, finding="OK"),
        efficiency=EfficiencyRating(rating=5, passed=True, finding="Slow"),
    )
    with patch("services.session_manager.session_store"):
        session, action = manager.reconcile_code_submission(
            session=fresh_session,
            output=output,
            intent=FollowUpIntent.ESCALATE,
            force_close=True,
            blueprint=_BLUEPRINT,
            time_remaining=600,
            min_time=600,
        )
    assert action == NextAction.CLOSE
    assert session.closed is True
    assert session.report is not None
    assert session.report.final_score >= 0


def test_strong_depth_forces_close(manager, fresh_session):
    fresh_session.stage = Stage.FOLLOWUP_CONVERSATIONAL
    output = ConversationalEvalOutput(
        finding="Excellent understanding.",
        candidate_depth=CandidateDepth.STRONG,
        answer_rating=9,
        follow_up=_follow_up(),
    )
    with patch("services.session_manager.session_store"):
        session, action = manager.reconcile_conversational_answer(
            session=fresh_session,
            output=output,
            intent=FollowUpIntent.ESCALATE,
            force_close=False,
            blueprint=_BLUEPRINT,
            time_remaining=2000,
            min_time=600,
        )
    assert action == NextAction.CLOSE
    assert session.closed is True


def test_score_math_determinism(manager, fresh_session):
    """Compute report twice with same inputs → same finalScore."""
    fresh_session.submissions = []
    fresh_session.answer_ratings = [7, 8]

    output = CodeEvalOutput(
        correctness=CorrectnessRating(rating=8, passed=True, finding="Good"),
        efficiency=EfficiencyRating(rating=6, passed=True, finding="OK"),
    )
    report1 = manager._compute_report(fresh_session, output, _BLUEPRINT, 2000, False)
    report2 = manager._compute_report(fresh_session, output, _BLUEPRINT, 2000, False)

    assert report1.final_score == report2.final_score
    assert "correctness" in report1.dimensions
    assert "efficiency" in report1.dimensions


def test_time_not_in_final_score(manager, fresh_session):
    """finalScore must be identical regardless of time_remaining."""
    output = CodeEvalOutput(
        correctness=CorrectnessRating(rating=8, passed=True, finding="Good"),
        efficiency=EfficiencyRating(rating=6, passed=True, finding="OK"),
    )
    report_early = manager._compute_report(fresh_session, output, _BLUEPRINT, 3000, False)
    report_late = manager._compute_report(fresh_session, output, _BLUEPRINT, 700, False)
    # pace.gate_fired differs but finalScore must not
    assert report_early.final_score == report_late.final_score


def test_four_turn_cap(manager, fresh_session):
    fresh_session.turn_count = 4  # already at cap
    output = ConversationalEvalOutput(
        finding="Average answer.",
        candidate_depth=CandidateDepth.ADEQUATE,
        answer_rating=6,
        follow_up=_follow_up(),
    )
    with patch("services.session_manager.session_store"):
        session, action = manager.reconcile_conversational_answer(
            session=fresh_session,
            output=output,
            intent=FollowUpIntent.ESCALATE,
            force_close=False,
            blueprint=_BLUEPRINT,
            time_remaining=2000,
            min_time=600,
        )
    assert action == NextAction.CLOSE
    assert session.closed is True
