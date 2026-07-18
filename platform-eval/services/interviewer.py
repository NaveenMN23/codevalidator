"""
Prompt builder — deterministic, no LLM.
Stable-prefix-first: large static content (persona + blueprint + gold-master)
goes in system_prompt so OpenAI prefix caching applies on turns 2+.
"""
import json
from models.dtos import FollowUpFormat, FollowUpIntent

_PERSONA = """You are a senior software engineer conducting a technical interview.
Your role is to evaluate the candidate's code or answer and then engage them in a focused follow-up conversation.
You reason about code quality; you never execute code.
Be precise, fair, and grounded in the blueprint criteria.

Interaction style:
- Always acknowledge the candidate's submission or answer in 1-3 sentences before asking the follow-up.
  Reference something specific they did (correctly or incorrectly). This makes the interview feel natural.
- Then ask exactly one follow-up question.
- Keep your tone professional but encouraging.

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
        preferred_fmt = a.get("preferredFormat", "")
        priority = a.get("priority", 2)
        line = f"- [{priority}] {area}: {scope}"
        if preferred_fmt:
            line += f"\n  Preferred format: {preferred_fmt}"
        if probe:
            line += f"\n  Suggested probe: {probe}"
        if indicator:
            line += f"\n  Strong answer looks like: {indicator}"
        lines.append(line)
    return "\n".join(lines)


def _format_remaining_areas(all_areas: list[dict], probed_areas: list[str]) -> str:
    """Returns focus areas not yet probed, sorted by priority ascending (1 = highest)."""
    remaining = [a for a in all_areas if a.get("area", "") not in probed_areas]
    remaining_sorted = sorted(remaining, key=lambda a: a.get("priority", 2))
    if not remaining_sorted:
        return "(all focus areas have been covered)"
    lines = []
    for a in remaining_sorted:
        area = a.get("area", "")
        scope = a.get("scope", "")
        probe = a.get("probeQuestion", "")
        indicator = a.get("goodAnswerIndicator", "")
        preferred_fmt = a.get("preferredFormat", "")
        priority = a.get("priority", 2)
        line = f"- [{priority}] {area}: {scope}"
        if preferred_fmt:
            line += f"\n  Preferred format: {preferred_fmt}"
        if probe:
            line += f"\n  Suggested probe: {probe}"
        if indicator:
            line += f"\n  Strong answer: {indicator}"
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


def _format_implementation_challenges(challenges: list[dict]) -> str:
    if not challenges:
        return "(none specified)"
    lines = []
    for c in challenges:
        cid = c.get("id", "")
        trigger = c.get("trigger", "")
        instruction = c.get("instruction", "")
        criteria = c.get("acceptanceCriteria", "")
        line = f"- [{cid}] Trigger: {trigger}\n  Instruction: {instruction}"
        if criteria:
            line += f"\n  Acceptance: {criteria}"
        lines.append(line)
    return "\n".join(lines)


def _intent_instruction(intent: FollowUpIntent, legal_formats: list[FollowUpFormat], difficulty: str) -> str:
    format_names = ", ".join(f.value for f in legal_formats) if legal_formats else "TEXT"
    intent_map = {
        FollowUpIntent.ESCALATE: (
            f"ESCALATE: the candidate solved the problem well. "
            f"Push them toward a harder concept from scaleUpDimensions or implementationChallenges. "
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
        "acknowledgment": "<1-3 sentences acknowledging the candidate's code — what they did well, any notable gap, natural transition to follow-up. Required even when closing.>",
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
            "question": "<string — the follow-up question to ask the candidate>",
            "chosen_area": "<area name from remaining focus areas, or null if CLOSE>",
            "options": "<list[string] or null — only for MCQ/TRUE_FALSE>",
            "expected_answer_key": "<string or null — correct letter/value, never shown to candidate>"
        },
        "communication_finding": "<string or null>"
    }, indent=2)


def _format_schema_conversational_eval() -> str:
    return json.dumps({
        "acknowledgment": "<1-3 sentences acknowledging the candidate's answer — what was right, what was missing, natural transition. Required even when closing.>",
        "finding": "<string — evaluation of the candidate's answer>",
        "candidate_depth": "<SHALLOW|ADEQUATE|STRONG>",
        "answer_rating": "<int 1-10>",
        "follow_up": {
            "intent": "<ESCALATE|CONSOLIDATE|QUICK_PROBE|QUICK_CLOSE|CLOSE>",
            "type": "<CONVERSATIONAL|IMPLEMENTATION>",
            "format": "<TEXT|CODE|MCQ|TRUE_FALSE|COMPLEXITY>",
            "question": "<string — the next question to ask the candidate>",
            "chosen_area": "<area name from remaining focus areas, or null if CLOSE>",
            "options": "<list[string] or null — only for MCQ/TRUE_FALSE>",
            "expected_answer_key": "<string or null — correct letter/value, never shown to candidate>"
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
    probed_areas: list[str] | None = None,
) -> tuple[str, str]:
    """Returns (system_prompt, user_message) for a CODE_SUBMISSION turn."""
    probed_areas = probed_areas or []
    task = blueprint.get("task", {})
    evaluation = blueprint.get("evaluation", {})
    follow_up_ctx = blueprint.get("followUpContext", {})
    rubric = evaluation.get("rubric", "Evaluate correctness and efficiency.")
    all_focus_areas = follow_up_ctx.get("interviewerFocusAreas", [])
    scale_up = follow_up_ctx.get("scaleUpDimensions", [])
    expected_complexity = task.get("expectedComplexity", {})
    common_mistakes = evaluation.get("commonMistakes", [])
    seniority_signals = evaluation.get("senioritySignals", [])
    expected_approaches = follow_up_ctx.get("expectedApproaches", [])
    known_edge_cases = follow_up_ctx.get("knownEdgeCases", [])
    implementation_challenges = follow_up_ctx.get("implementationChallenges", [])

    # System prompt: stable prefix (persona + blueprint + gold-master)
    system_prompt = f"""{_PERSONA}

=== TASK ===
Description: {task.get('description', 'N/A')}
Language: {task.get('language', 'N/A')}
Constraints: {json.dumps(task.get('constraints', []))}
Expected complexity: {json.dumps(expected_complexity)}
Difficulty: {difficulty}

=== RUBRIC ===
{rubric if isinstance(rubric, str) else json.dumps(rubric, indent=2)}

=== SENIORITY SIGNALS ===
{json.dumps(seniority_signals)}

=== ALL INTERVIEWER FOCUS AREAS ===
{_format_focus_areas(all_focus_areas)}

=== EXPECTED APPROACHES ===
{_format_approaches(expected_approaches)}

=== KNOWN EDGE CASES ===
{_format_edge_cases(known_edge_cases)}

=== SCALE-UP DIMENSIONS ===
{_format_scale_up(scale_up)}

=== IMPLEMENTATION CHALLENGES (for CODE-type follow-ups) ===
{_format_implementation_challenges(implementation_challenges)}

=== COMMON MISTAKES TO PROBE ===
{json.dumps(common_mistakes)}

=== GOLD-MASTER SOLUTION (reference) ===
{_format_files(gold_master_files)}
"""

    # Probed areas context for the LLM
    probed_text = ""
    if probed_areas:
        probed_text = f"\n=== ALREADY PROBED AREAS (do NOT repeat) ===\n{', '.join(probed_areas)}\n"

    remaining_text = f"\n=== REMAINING FOCUS AREAS (pick from these, highest priority first) ===\n{_format_remaining_areas(all_focus_areas, probed_areas)}\n"

    history_text = ""
    if history:
        history_text = "\n=== CONVERSATION HISTORY ===\n" + "\n".join(
            f"[{t.get('role')}] {t.get('content', '')[:500]}" for t in history
        )

    user_message = f"""=== CANDIDATE SUBMISSION ===
{_format_files(candidate_files)}

=== TIME REMAINING ===
{time_remaining} seconds
{probed_text}{remaining_text}{history_text}

=== YOUR TASK ===
1. Write acknowledgment (1-3 sentences): reference something specific in the candidate's code.
   If they did well, say so. If they missed something, name it concisely. End with a natural
   transition into the follow-up (e.g. "Let's dig into...").
2. Rate correctness and efficiency 1–10 against the rubric.
3. {_intent_instruction(intent, legal_formats, difficulty)}
   - Pick chosen_area from REMAINING FOCUS AREAS (highest priority first).
   - For MCQ/TRUE_FALSE: populate options[] as lettered strings (e.g. "A) ...")
     and set expected_answer_key to the correct letter. Do NOT reveal expected_answer_key in the question.
   - For COMPLEXITY: ask for time/space complexity or scalability estimate.
   - For CODE (IMPLEMENTATION): reference an implementationChallenge that fits what you observed.
4. Set follow_up to null if intent is CLOSE. Still write acknowledgment.

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
    probed_areas: list[str] | None = None,
) -> tuple[str, str]:
    """Returns (system_prompt, user_message) for a CONVERSATIONAL_ANSWER turn."""
    probed_areas = probed_areas or []
    task = blueprint.get("task", {})
    all_focus_areas = blueprint.get("followUpContext", {}).get("interviewerFocusAreas", [])

    system_prompt = f"""{_PERSONA}

=== TASK CONTEXT ===
Description: {task.get('description', 'N/A')}
Difficulty: {difficulty}

=== ALL INTERVIEWER FOCUS AREAS ===
{_format_focus_areas(all_focus_areas)}
"""

    follow_up_ctx = ""
    if active_follow_up:
        follow_up_ctx = (
            f"\n=== ACTIVE FOLLOW-UP (question the candidate just answered) ===\n"
            f"Area: {active_follow_up.get('chosen_area', 'unknown')}\n"
            f"Question: {active_follow_up.get('question', '')}\n"
            f"Format: {active_follow_up.get('format', '')}\n"
        )
        if active_follow_up.get("options"):
            follow_up_ctx += f"Options: {active_follow_up['options']}\n"
        if active_follow_up.get("expected_answer_key"):
            follow_up_ctx += f"Correct answer key: {active_follow_up['expected_answer_key']}\n"

    probed_text = ""
    if probed_areas:
        probed_text = f"\n=== ALREADY PROBED AREAS (do NOT repeat) ===\n{', '.join(probed_areas)}\n"

    remaining_text = f"\n=== REMAINING FOCUS AREAS (pick from these, highest priority first) ===\n{_format_remaining_areas(all_focus_areas, probed_areas)}\n"

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
{probed_text}{remaining_text}{history_text}

=== YOUR TASK ===
1. Write acknowledgment (1-3 sentences): reference something specific in the candidate's answer.
   If they got it right, acknowledge it precisely. If partially right, note what they captured and
   what they missed. If wrong, gently correct. End with a transition into the next question.
2. Evaluate their answer: finding + candidate_depth (SHALLOW/ADEQUATE/STRONG) + answer_rating 1–10.
3. {_intent_instruction(intent, legal_formats, difficulty)}
   - Pick chosen_area from REMAINING FOCUS AREAS (highest priority first).
   - For MCQ/TRUE_FALSE: populate options[] and expected_answer_key.
   - Set follow_up to null if intent is CLOSE. Still write acknowledgment.

Respond ONLY with JSON matching this schema:
{_format_schema_conversational_eval()}"""

    return system_prompt, user_message
