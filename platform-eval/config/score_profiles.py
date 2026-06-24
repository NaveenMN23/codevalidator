from __future__ import annotations

SCORE_PROFILES: dict[str, dict[str, int]] = {
    "EASY": {
        "correctness": 45,
        "efficiency": 20,
        "followUp": 20,
        "communication": 15,
    },
    "MEDIUM": {
        "correctness": 40,
        "efficiency": 25,
        "followUp": 20,
        "communication": 15,
    },
    "HARD": {
        "correctness": 30,
        "efficiency": 20,
        "followUp": 30,
        "designJudgment": 20,
    },
    "default": {
        "correctness": 40,
        "efficiency": 20,
        "followUp": 25,
        "communication": 15,
    },
}


def get_profile(difficulty: str, target_role: str | None = None) -> dict[str, int]:
    return SCORE_PROFILES.get(difficulty.upper(), SCORE_PROFILES["default"])
