import pytest
from models.dtos import CandidateDepth, FollowUpIntent, FollowUpFormat
from services.steering import select_intent_and_formats, compute_max_turns, MAX_TURNS


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


def test_compute_max_turns_easy_caps_at_2():
    assert compute_max_turns(3000, 600, "EASY") == 2


def test_compute_max_turns_hard_gets_4():
    assert compute_max_turns(3000, 600, "HARD") == 4


def test_compute_max_turns_shrinks_with_low_time():
    # ratio ≈ 1.3x → should be max(base-2, 1)
    assert compute_max_turns(800, 600, "MEDIUM") == 1


def test_compute_max_turns_medium_with_moderate_time():
    # ratio = 2.5x → max(3-1, 1) = 2
    assert compute_max_turns(1500, 600, "MEDIUM") == 2


def test_hard_difficulty_biases_escalate():
    # HARD should prefer ESCALATE even when correctness is ambiguous
    intent, formats = select_intent_and_formats(
        time_remaining=2000, min_time=600,
        correctness_passed=False, candidate_depth=None,
        difficulty="HARD", turn_count=0,
    )
    # hard_bias makes much_time + HARD → ESCALATE regardless of correctness
    assert intent == FollowUpIntent.ESCALATE


def test_custom_max_turns_overrides_global():
    # With max_turns=1, a turn_count=1 should close
    intent, formats = select_intent_and_formats(
        time_remaining=3000, min_time=600,
        correctness_passed=True, candidate_depth=None,
        difficulty="MEDIUM", turn_count=1,
        max_turns=1,
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
