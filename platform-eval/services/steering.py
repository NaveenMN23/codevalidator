"""
Policy matrix — pure deterministic logic, no LLM.
session_manager calls this to pick intent + legal formats before each LLM call.
"""
from __future__ import annotations
from models.dtos import FollowUpIntent, FollowUpFormat, CandidateDepth

# Maximum follow-up turns before forced close
MAX_TURNS = 4

# "Much time" threshold: time > 2 × min_time
_MUCH_TIME_MULTIPLIER = 2


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
) -> tuple[FollowUpIntent, list[FollowUpFormat]]:
    """
    Returns (intent, legal_formats).
    CLOSE always means no follow-up question should be generated.
    """
    # Hard close conditions
    if turn_count >= MAX_TURNS:
        return FollowUpIntent.CLOSE, []
    if candidate_depth == CandidateDepth.STRONG:
        return FollowUpIntent.CLOSE, []
    if time_remaining <= min_time:
        return FollowUpIntent.CLOSE, []

    clean = _is_clean(correctness_passed, candidate_depth)
    much_time = time_remaining > _MUCH_TIME_MULTIPLIER * min_time

    if much_time and clean:
        formats = [FollowUpFormat.MCQ, FollowUpFormat.COMPLEXITY]
        # IMPLEMENTATION only if there is substantial time AND not already in implementation mode
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
