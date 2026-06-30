from services import interviewer
from models.dtos import FollowUpIntent, FollowUpFormat


_BLUEPRINT = {
    "task": {
        "description": "Implement dispense product logic",
        "constraints": ["Must update stock", "Must handle insufficient funds"],
        "difficulty": "EASY",
        "expectedComplexity": {"time": "O(1)", "space": "O(1)"},
    },
    "rubric": "Check stock update and fund deduction.",
    "followUpContext": {
        "interviewerFocusAreas": [
            {"area": "atomicity", "scope": "Is stock decrement atomic?", "hint": "Think about concurrent access."}
        ],
        "scaleUpDimensions": ["concurrent vending", "distributed inventory"],
        "commonMistakes": ["forgetting to decrement stock"],
    },
}

_GOLD_FILES = {"src/VendingMachine.java": "// gold master"}
_CANDIDATE_FILES = {"src/VendingMachine.java": "// candidate solution"}


def test_code_submission_messages_structure():
    system, user = interviewer.build_code_submission_messages(
        blueprint=_BLUEPRINT,
        gold_master_files=_GOLD_FILES,
        candidate_files=_CANDIDATE_FILES,
        intent=FollowUpIntent.ESCALATE,
        legal_formats=[FollowUpFormat.MCQ, FollowUpFormat.COMPLEXITY],
        history=[],
        time_remaining=3000,
        difficulty="EASY",
    )
    # System prompt should contain static blueprint content
    assert "dispense product logic" in system
    assert "gold master" in system
    # User message contains dynamic candidate content
    assert "candidate solution" in user
    assert "MCQ" in user or "ESCALATE" in user


def test_system_prompt_before_user_message():
    system, user = interviewer.build_code_submission_messages(
        blueprint=_BLUEPRINT,
        gold_master_files=_GOLD_FILES,
        candidate_files=_CANDIDATE_FILES,
        intent=FollowUpIntent.ESCALATE,
        legal_formats=[FollowUpFormat.MCQ],
        history=[],
        time_remaining=2000,
        difficulty="MEDIUM",
    )
    # The stable prefix (blueprint/gold-master) must be in system, not user
    assert "gold master" in system
    assert "candidate solution" in user


def test_answer_messages_structure():
    system, user = interviewer.build_answer_messages(
        blueprint=_BLUEPRINT,
        active_follow_up={
            "question": "Is decrement atomic?",
            "format": "TRUE_FALSE",
            "options": ["A) True", "B) False"],
            "expected_answer_key": "B",
        },
        candidate_answer="I think it is atomic because I used synchronized.",
        intent=FollowUpIntent.CONSOLIDATE,
        legal_formats=[FollowUpFormat.TEXT, FollowUpFormat.TRUE_FALSE],
        history=[],
        time_remaining=1800,
        difficulty="EASY",
    )
    assert "atomic" in user or "dispense" in system
    assert "synchronized" in user


def test_mcq_format_instruction_present():
    system, user = interviewer.build_code_submission_messages(
        blueprint=_BLUEPRINT,
        gold_master_files={},
        candidate_files={"src/f.java": "code"},
        intent=FollowUpIntent.QUICK_PROBE,
        legal_formats=[FollowUpFormat.MCQ, FollowUpFormat.TRUE_FALSE],
        history=[],
        time_remaining=1200,
        difficulty="EASY",
    )
    # MCQ rendering instruction should be present
    assert "MCQ" in user or "options" in user
