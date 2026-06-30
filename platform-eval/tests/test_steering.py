import pytest
from models.dtos import CandidateDepth, FollowUpIntent, FollowUpFormat
from services.steering import select_intent_and_formats, MAX_TURNS


MIN_TIME = 600


def test_time_gate_fires():
    intent, formats = select_intent_and_formats(
        time_remaining=600, min_time=600,
        correctness_passed=True, candidate_depth=None,
        difficulty="EASY", turn_count=0,
    )
    assert intent == FollowUpIntent.CLOSE
    assert formats == []


def test_time_below_gate():
    intent, formats = select_intent_and_formats(
        time_remaining=500, min_time=600,
        correctness_passed=True, candidate_depth=None,
        difficulty="EASY", turn_count=0,
    )
    assert intent == FollowUpIntent.CLOSE


def test_escalate_clean_much_time():
    intent, formats = select_intent_and_formats(
        time_remaining=3000, min_time=600,
        correctness_passed=True, candidate_depth=CandidateDepth.ADEQUATE,
        difficulty="MEDIUM", turn_count=0,
    )
    assert intent == FollowUpIntent.ESCALATE
    assert FollowUpFormat.MCQ in formats
    assert FollowUpFormat.COMPLEXITY in formats


def test_consolidate_struggled_much_time():
    intent, formats = select_intent_and_formats(
        time_remaining=2000, min_time=600,
        correctness_passed=False, candidate_depth=CandidateDepth.SHALLOW,
        difficulty="MEDIUM", turn_count=0,
    )
    assert intent == FollowUpIntent.CONSOLIDATE
    assert FollowUpFormat.TEXT in formats


def test_quick_probe_clean_little_time():
    intent, formats = select_intent_and_formats(
        time_remaining=900, min_time=600,  # 1.5x min, not much time
        correctness_passed=True, candidate_depth=CandidateDepth.ADEQUATE,
        difficulty="EASY", turn_count=1,
    )
    assert intent == FollowUpIntent.QUICK_PROBE
    assert FollowUpFormat.MCQ in formats


def test_quick_close_struggled_little_time():
    intent, formats = select_intent_and_formats(
        time_remaining=800, min_time=600,
        correctness_passed=False, candidate_depth=CandidateDepth.SHALLOW,
        difficulty="EASY", turn_count=1,
    )
    assert intent == FollowUpIntent.QUICK_CLOSE
    assert FollowUpFormat.TRUE_FALSE in formats


def test_strong_depth_forces_close():
    intent, formats = select_intent_and_formats(
        time_remaining=3000, min_time=600,
        correctness_passed=True, candidate_depth=CandidateDepth.STRONG,
        difficulty="HARD", turn_count=1,
    )
    assert intent == FollowUpIntent.CLOSE


def test_max_turns_forces_close():
    intent, formats = select_intent_and_formats(
        time_remaining=3000, min_time=600,
        correctness_passed=True, candidate_depth=CandidateDepth.ADEQUATE,
        difficulty="MEDIUM", turn_count=MAX_TURNS,
    )
    assert intent == FollowUpIntent.CLOSE


def test_implementation_only_with_substantial_time():
    # 3x min time → CODE should be present
    intent, formats = select_intent_and_formats(
        time_remaining=1900, min_time=600,  # 1900 > 3*600=1800
        correctness_passed=True, candidate_depth=CandidateDepth.ADEQUATE,
        difficulty="HARD", turn_count=0,
    )
    assert intent == FollowUpIntent.ESCALATE
    assert FollowUpFormat.CODE in formats

    # Just 2x min time → CODE should NOT be present
    intent2, formats2 = select_intent_and_formats(
        time_remaining=1300, min_time=600,  # > 2*600 but < 3*600
        correctness_passed=True, candidate_depth=CandidateDepth.ADEQUATE,
        difficulty="HARD", turn_count=0,
    )
    assert intent2 == FollowUpIntent.ESCALATE
    assert FollowUpFormat.CODE not in formats2
