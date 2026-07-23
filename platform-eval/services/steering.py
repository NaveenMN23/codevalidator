"""
Policy matrix — pure deterministic logic, no LLM.
session_manager calls this to pick intent + legal formats before each LLM call.
"""
from __future__ import annotations
from models.dtos import FollowUpIntent, FollowUpFormat, CandidateDepth

# Absolute ceiling on follow-up turns (safety net; dynamic budget is preferred)
MAX_TURNS = 4

# "Much time" threshold: time > 2 × min_time
_MUCH_TIME_MULTIPLIER = 2


def compute_max_turns(time_remaining: int, min_time: int, difficulty: str) -> int:
    """
    Dynamic turn cap based on available time and difficulty.
    HARD problems get more depth when time allows; EASY problems stay shallow.
    """
    ratio = time_remaining / max(min_time, 1)
    base = {"HARD": 4, "MEDIUM": 3, "EASY": 2}.get(difficulty.upper(), 3)
    if ratio > 3:
        return base
    elif ratio > 2:
        return max(base - 1, 1)
    elif ratio > 1.5:
        return max(base - 2, 1)
    return 1


def _is_clean(correctness_passed: bool, candidate_depth: CandidateDepth | None) -> bool:
    if not correctness_passed:
        return False
    if candidate_depth in (CandidateDepth.ADEQUATE, CandidateDepth.STRONG):
        return True
    return correctness_passed and candidate_depth is None


def select_intent_and_formats(
    time_remaining: int,
    min_time: int,
    correctness_passed: bool,
    candidate_depth: CandidateDepth | None,
    difficulty: str,
    turn_count: int,
    max_turns: int = MAX_TURNS,
) -> tuple[FollowUpIntent, list[FollowUpFormat]]:
    """
    Returns (intent, legal_formats).
    CLOSE always means no follow-up question should be generated.
    max_turns overrides the global MAX_TURNS for time-budget-aware control.
    """
    # Hard close conditions
    if turn_count >= max_turns:
        return FollowUpIntent.CLOSE, []
    if candidate_depth == CandidateDepth.STRONG:
        return FollowUpIntent.CLOSE, []
    if time_remaining <= min_time:
        return FollowUpIntent.CLOSE, []

    clean = _is_clean(correctness_passed, candidate_depth)
    much_time = time_remaining > _MUCH_TIME_MULTIPLIER * min_time

    # HARD problems bias toward ESCALATE sooner — design judgment matters more
    hard_bias = difficulty.upper() == "HARD"

    if much_time and (clean or hard_bias):
        formats = [FollowUpFormat.MCQ, FollowUpFormat.COMPLEXITY]
        if time_remaining > 3 * min_time:
            formats.insert(0, FollowUpFormat.CODE)
        return FollowUpIntent.ESCALATE, formats

    if much_time and not clean:
        return FollowUpIntent.CONSOLIDATE, [
            FollowUpFormat.TEXT,
            FollowUpFormat.COMPLEXITY,
            FollowUpFormat.TRUE_FALSE,
        ]

    if not much_time and clean:
        return FollowUpIntent.QUICK_PROBE, [
            FollowUpFormat.MCQ,
            FollowUpFormat.TRUE_FALSE,
            FollowUpFormat.COMPLEXITY,
        ]

    # little time + struggled
    return FollowUpIntent.QUICK_CLOSE, [FollowUpFormat.TRUE_FALSE, FollowUpFormat.TEXT]


def validate_follow_up(
    follow_up_format: FollowUpFormat,
    follow_up_intent: FollowUpIntent,
    legal_formats: list[FollowUpFormat],
    open_areas: list[str],
    chosen_area: str | None,
) -> bool:
    """Returns True if the LLM's follow-up passes the in-scope + format guardrail."""
    if follow_up_format not in legal_formats:
        return False
    if open_areas and chosen_area and chosen_area not in open_areas:
        return False
    return True


def build_templated_fallback(area: str, scope: str, hint: str, intent: FollowUpIntent) -> str:
    """Deterministic fallback follow-up question when LLM output fails validation."""
    if intent in (FollowUpIntent.ESCALATE, FollowUpIntent.QUICK_PROBE):
        return f"Regarding {area}: {scope}. Can you explain your approach? {hint}"
    return f"Regarding {area}: {scope}. Can you confirm your understanding? {hint}"
