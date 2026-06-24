from config.score_profiles import get_profile, SCORE_PROFILES


def test_easy_profile():
    p = get_profile("EASY")
    assert p["correctness"] == 45
    assert sum(p.values()) == 100


def test_hard_profile():
    p = get_profile("HARD")
    assert "designJudgment" in p
    assert sum(p.values()) == 100


def test_case_insensitive():
    assert get_profile("easy") == get_profile("EASY")
    assert get_profile("medium") == get_profile("MEDIUM")


def test_fallback_on_unknown():
    p = get_profile("UNKNOWN_TIER")
    assert p == SCORE_PROFILES["default"]
    assert sum(p.values()) == 100
