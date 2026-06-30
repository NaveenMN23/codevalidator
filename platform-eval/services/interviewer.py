"""
Prompt builder — deterministic, no LLM.
Stable-prefix-first: large static content (persona + blueprint + gold-master)
goes in system_prompt so OpenAI prefix caching applies on turns 2+.
"""
import json
from models.dtos import FollowUpFormat, FollowUpIntent

_PERSONA = """You are a senior software engineer conducting a technical interview.
Your role is to evaluate the candidate's code submission and conduct a focused follow-up interview.
You reason about code quality; you never execute code.
Be precise, fair, and grounded in the blueprint criteria.
Respond ONLY with valid JSON matching the schema described in the user message."""


def _format_files(file_map: dict[str, str]) -> str:
    if not file_map:
        return "(no files)"
    parts = []
    for path in sorted(file_map.keys()):
        parts.append(f"### {path}\n```\n{file_map[path]}\n```")
    return "\n\n".join(parts)


def _format_focus_areas(areas: list[dict]) -> str:
    if not areas:
        return "(no specific focus areas)"
    lines = []
    for a in areas:
        area = a.get("area", "")
        scope = a.get("scope", "")
        probe = a.get("probeQuestion", "")
        indicator = a.get("goodAnswerIndicator", "")
        line = f"- {area}: {scope}"
        if probe:
            line += f"\n  Probe question: {probe}"
        if indicator:
            line += f"\n  Strong answer looks like: {indicator}"
        lines.append(line)
    return "\n".join(lines)


def _format_edge_cases(cases: list) -> str:
    if not cases:
        return "(none specified)"
    lines = []
    for c in cases:
        if isinstance(c, dict):
            case = c.get("case", "")
            handling = c.get("expectedHandling", "")
            followup = c.get("followUpIfMissed")
            line = f"- {case}"
            if handling:
                line += f"\n  Expected: {handling}"
            if followup:
                line += f"\n  Ask if missed: {followup}"
        else:
            line = f"- {c}"
        lines.append(line)
    return "\n".join(lines)


def _format_approaches(approaches: list[dict]) -> str:
    if not approaches:
        return "(none specified)"
    lines = []
    for a in approaches:
        approach = a.get("approach", "")
        tradeoff = a.get("tradeoff", "")
        rating = a.get("rating", "")
        line = f"- {approach}"
        if tradeoff:
            line += f" — {tradeoff}"
        if rating:
            line += f" (expected score: {rating})"
        lines.append(line)
    return "\n".join(lines)


def _format_scale_up(dimensions: list) -> str:
    if not dimensions:
        return "(none specified)"
    lines = []
    for d in dimensions:
        if isinstance(d, dict):
            dim = d.get("dimension", "")
            trigger = d.get("triggerCondition", "")
            line = f"- {dim}"
            if trigger:
                line += f" [trigger: {trigger}]"
        else:
            line = f"- {d}"
        lines.append(line)
    return "\n".join(lines)


def _intent_instruction(intent: FollowUpIntent, legal_formats: list[FollowUpFormat], difficulty: str) -> str:
    format_names = ", ".join(f.value for f in legal_formats) if legal_formats else "TEXT"
    intent_map = {
        FollowUpIntent.ESCALATE: (
            f"ESCALATE: the candidate solved the problem well. "
            f"Push them toward a harder concept from scaleUpDimensions. "
            f"Difficulty tier is {difficulty}."
        ),
        FollowUpIntent.CONSOLIDATE: (
            "CONSOLIDATE: the candidate struggled. "
            "Help them understand what they missed via a guided question."
        ),
        FollowUpIntent.QUICK_PROBE: (
            "QUICK_PROBE: time is short. Ask one fast, targeted question to gather a signal."
        ),
        FollowUpIntent.QUICK_CLOSE: (
            "QUICK_CLOSE: time is very short. Ask one brief closing question then close."
        ),
        FollowUpIntent.CLOSE: (
            "CLOSE: do not generate a follow-up question. Set follow_up to null."
        ),
    }
    return (
        f"Follow-up intent: {intent_map.get(intent, intent.value)}\n"
        f"Allowed formats: {format_names}"
    )


def _format_schema_code_eval() -> str:
    return json.dumps({
        "correctness": {
            "rating": "<int 1-10>",
            "passed": "<bool>",
            "finding": "<string>"
        },
        "efficiency": {
            "rating": "<int 1-10>",
            "passed": "<bool>",
            "finding": "<string>"
        },
        "follow_up": {
            "intent": "<ESCALATE|CONSOLIDATE|QUICK_PROBE|QUICK_CLOSE|CLOSE>",
            "type": "<CONVERSATIONAL|IMPLEMENTATION>",
            "format": "<TEXT|CODE|MCQ|TRUE_FALSE|COMPLEXITY>",
            "question": "<string>",
            "options": "<list[string] or null>",
            "expected_answer_key": "<string or null>"
        },
        "communication_finding": "<string or null>"
    }, indent=2)


def _format_schema_conversational_eval() -> str:
    return json.dumps({
        "finding": "<string>",
        "candidate_depth": "<SHALLOW|ADEQUATE|STRONG>",
        "answer_rating": "<int 1-10>",
        "follow_up": {
            "intent": "<ESCALATE|CONSOLIDATE|QUICK_PROBE|QUICK_CLOSE|CLOSE>",
            "type": "<CONVERSATIONAL|IMPLEMENTATION>",
            "format": "<TEXT|CODE|MCQ|TRUE_FALSE|COMPLEXITY>",
            "question": "<string>",
            "options": "<list[string] or null>",
            "expected_answer_key": "<string or null>"
        },
        "communication_finding": "<string or null>"
    }, indent=2)


def build_code_submission_messages(
    blueprint: dict,
    gold_master_files: dict[str, str],
    candidate_files: dict[str, str],
    intent: FollowUpIntent,
    legal_formats: list[FollowUpFormat],
    history: list[dict],
    time_remaining: int,
    difficulty: str = "MEDIUM",
) -> tuple[str, str]:
    """Returns (system_prompt, user_message) for a CODE_SUBMISSION turn."""
    task = blueprint.get("task", {})
    evaluation = blueprint.get("evaluation", {})
    follow_up_ctx = blueprint.get("followUpContext", {})
    rubric = evaluation.get("rubric", "Evaluate correctness and efficiency.")
    focus_areas = follow_up_ctx.get("interviewerFocusAreas", [])
    scale_up = follow_up_ctx.get("scaleUpDimensions", [])
    expected_complexity = task.get("expectedComplexity", {})
    common_mistakes = evaluation.get("commonMistakes", [])
    seniority_signals = evaluation.get("senioritySignals", [])
    expected_approaches = follow_up_ctx.get("expectedApproaches", [])
    known_edge_cases = follow_up_ctx.get("knownEdgeCases", [])

    # System prompt: stable prefix (persona + blueprint + gold-master)
    system_prompt = f"""{_PERSONA}

=== TASK ===
Description: {task.get('description', 'N/A')}
Language: {task.get('language', 'N/A')}
Constraints: {json.dumps(task.get('constraints', []))}
Expected complexity: {json.dumps(expected_complexity)}
Difficulty: {difficulty}

=== RUBRIC ===
{rubric}

=== SENIORITY SIGNALS ===
{json.dumps(seniority_signals)}

=== INTERVIEWER FOCUS AREAS ===
{_format_focus_areas(focus_areas)}

=== EXPECTED APPROACHES ===
{_format_approaches(expected_approaches)}

=== KNOWN EDGE CASES ===
{_format_edge_cases(known_edge_cases)}

=== SCALE-UP DIMENSIONS ===
{_format_scale_up(scale_up)}

=== COMMON MISTAKES TO PROBE ===
{json.dumps(common_mistakes)}

=== GOLD-MASTER SOLUTION (reference) ===
{_format_files(gold_master_files)}
"""

    # User message: dynamic (candidate files + intent + schema)
    history_text = ""
    if history:
        history_text = "\n=== CONVERSATION HISTORY ===\n" + "\n".join(
            f"[{t.get('role')}] {t.get('content', '')[:500]}" for t in history
        )

    user_message = f"""=== CANDIDATE SUBMISSION ===
{_format_files(candidate_files)}

=== TIME REMAINING ===
{time_remaining} seconds

{history_text}

=== YOUR TASK ===
1. Rate correctness and efficiency 1–10 against the rubric.
2. {_intent_instruction(intent, legal_formats, difficulty)}
   - For MCQ/TRUE_FALSE: populate options[] as lettered strings (e.g. "A) ...")
     and set expected_answer_key to the correct letter. Do NOT send expected_answer_key to the candidate.
   - For COMPLEXITY: ask for time/space complexity or scalability estimate.
   - For CODE (IMPLEMENTATION): ask the candidate to re-submit with a specific change.
3. Set follow_up to null if intent is CLOSE.

Respond ONLY with JSON matching this schema:
{_format_schema_code_eval()}"""

    return system_prompt, user_message


def build_answer_messages(
    blueprint: dict,
    active_follow_up: dict | None,
    candidate_answer: str,
    intent: FollowUpIntent,
    legal_formats: list[FollowUpFormat],
    history: list[dict],
    time_remaining: int,
    difficulty: str = "MEDIUM",
) -> tuple[str, str]:
    """Returns (system_prompt, user_message) for a CONVERSATIONAL_ANSWER turn."""
    task = blueprint.get("task", {})
    focus_areas = blueprint.get("followUpContext", {}).get("interviewerFocusAreas", [])

    system_prompt = f"""{_PERSONA}

=== TASK CONTEXT ===
Description: {task.get('description', 'N/A')}
Difficulty: {difficulty}

=== INTERVIEWER FOCUS AREAS ===
{_format_focus_areas(focus_areas)}
"""

    follow_up_ctx = ""
    if active_follow_up:
        follow_up_ctx = (
            f"\n=== ACTIVE FOLLOW-UP ===\n"
            f"Question: {active_follow_up.get('question', '')}\n"
            f"Format: {active_follow_up.get('format', '')}\n"
        )
        if active_follow_up.get("options"):
            follow_up_ctx += f"Options: {active_follow_up['options']}\n"
        if active_follow_up.get("expected_answer_key"):
            follow_up_ctx += f"Expected answer key: {active_follow_up['expected_answer_key']}\n"

    history_text = ""
    if history:
        history_text = "\n=== CONVERSATION HISTORY ===\n" + "\n".join(
            f"[{t.get('role')}] {t.get('content', '')[:400]}" for t in history
        )

    user_message = f"""{follow_up_ctx}

=== CANDIDATE ANSWER ===
{candidate_answer}

=== TIME REMAINING ===
{time_remaining} seconds

{history_text}

=== YOUR TASK ===
1. Evaluate the candidate's answer: finding + candidate_depth (SHALLOW/ADEQUATE/STRONG) + answer_rating 1–10.
2. {_intent_instruction(intent, legal_formats, difficulty)}
   - For MCQ/TRUE_FALSE: populate options[] and expected_answer_key.
   - Set follow_up to null if intent is CLOSE.

Respond ONLY with JSON matching this schema:
{_format_schema_conversational_eval()}"""

    return system_prompt, user_message
