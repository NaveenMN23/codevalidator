"""
Per-turn orchestrator: resolve → gate → steer → build → call → reconcile → persist.
One LLM call per turn.
"""
from models.dtos import (
    CodeSubmitRequest, CodeSubmitResponse, ConversationalAnswerRequest,
    ConversationalAnswerResponse, CodeEvalOutput, ConversationalEvalOutput,
    EvaluationBlock, FollowUpIntent, CandidateDepth, ConversationTurn,
)
from services.sources import blueprint_source, solution_source, _filter_files
from services.steering import select_intent_and_formats, validate_follow_up, build_templated_fallback
from services import interviewer
from services.llm_client import llm_client
from services.session_manager import session_manager
from infrastructure.logger import log


def handle_code_submission(request: CodeSubmitRequest) -> CodeSubmitResponse:
    session = session_manager.load_or_create(request.session_id, request.problem_id)

    if session.closed:
        raise ValueError(f"Session {request.session_id} is already closed")

    # Resolve blueprint + gold-master
    blueprint = blueprint_source.resolve(request.problem_id)
    gold_master = solution_source.resolve(request.gold_master_ref or "", blueprint)
    candidate_files = _filter_files(request.submission.changed_files, blueprint)

    difficulty = blueprint.get("task", {}).get("difficulty", "MEDIUM").upper()
    min_time = request.minimum_time_remaining_seconds

    # Time gate (before any LLM cost)
    if session_manager.is_gate_fired(request.time_remaining_seconds, min_time):
        log.info(f"[{request.session_id}] Time gate fired before LLM — force close")
        session, next_action = session_manager.close_without_llm(
            session, blueprint, request.time_remaining_seconds
        )
        session_manager.persist(session)
        return CodeSubmitResponse(
            session_id=session.session_id,
            stage=session.stage,
            evaluation=EvaluationBlock(
                correctness=None,
                efficiency=None,
                follow_up=None,
            ),
            candidate_depth=None,
            next_action=next_action,
            closed=True,
            report=session.report,
        )

    # Policy matrix
    intent, legal_formats = select_intent_and_formats(
        time_remaining=request.time_remaining_seconds,
        min_time=min_time,
        correctness_passed=True,  # eval is only invoked after all tests pass
        candidate_depth=None,  # first submission has no prior depth
        difficulty=difficulty,
        turn_count=session.turn_count,
    )

    # Build messages
    system_prompt, user_message = interviewer.build_code_submission_messages(
        blueprint=blueprint,
        gold_master_files=gold_master,
        candidate_files=candidate_files,
        intent=intent,
        legal_formats=legal_formats,
        history=[t.model_dump() for t in session.conversation_history],
        time_remaining=request.time_remaining_seconds,
        difficulty=difficulty,
    )

    # LLM call
    raw = llm_client.complete_json_cached(
        system_prompt=system_prompt,
        user_message=user_message,
        label=f"code-eval:{request.session_id}",
    )
    output = CodeEvalOutput.model_validate(raw)

    # Post-call validation + guardrail
    if output.follow_up and intent != FollowUpIntent.CLOSE:
        open_areas = [
            a.get("area", "") for a in
            blueprint.get("followUpContext", {}).get("interviewerFocusAreas", [])
        ]
        if not validate_follow_up(
            output.follow_up.format,
            intent,
            legal_formats,
            open_areas,
            chosen_area=None,
        ):
            log.warning(f"[{request.session_id}] Follow-up failed guardrail — using templated fallback")
            first_area = open_areas[0] if open_areas else "the implementation"
            output.follow_up.question = build_templated_fallback(
                area=first_area,
                scope=blueprint.get("followUpContext", {}).get("interviewerFocusAreas", [{}])[0].get("scope", "") if open_areas else "",
                hint="",
                intent=intent,
            )

    # Reconcile
    force_close = intent == FollowUpIntent.CLOSE
    session, next_action = session_manager.reconcile_code_submission(
        session=session,
        output=output,
        intent=intent,
        force_close=force_close,
        blueprint=blueprint,
        time_remaining=request.time_remaining_seconds,
        min_time=min_time,
    )
    session_manager.persist(session)

    follow_up_view = output.follow_up.candidate_view() if output.follow_up and not session.closed else None

    return CodeSubmitResponse(
        session_id=session.session_id,
        stage=session.stage,
        evaluation=EvaluationBlock(
            correctness=output.correctness,
            efficiency=output.efficiency,
            follow_up=follow_up_view,
        ),
        candidate_depth=None,
        next_action=next_action,
        closed=session.closed,
        report=session.report if session.closed else None,
    )


def handle_conversational_answer(request: ConversationalAnswerRequest) -> ConversationalAnswerResponse:
    session = session_manager.load_or_create(request.session_id, request.problem_id)

    if session.closed:
        raise ValueError(f"Session {request.session_id} is already closed")

    blueprint = blueprint_source.resolve(request.problem_id)
    difficulty = blueprint.get("task", {}).get("difficulty", "MEDIUM").upper()
    min_time = request.minimum_time_remaining_seconds

    # Time gate — short-circuits with no LLM call
    if session_manager.is_gate_fired(request.time_remaining_seconds, min_time):
        log.info(f"[{request.session_id}] Time gate fired — force close (no LLM)")
        session, next_action = session_manager.close_without_llm(
            session, blueprint, request.time_remaining_seconds
        )
        session_manager.persist(session)
        return ConversationalAnswerResponse(
            session_id=session.session_id,
            stage=session.stage,
            evaluation=EvaluationBlock(finding="Session closed due to time."),
            candidate_depth=None,
            next_action=next_action,
            closed=True,
            report=session.report,
        )

    # Append candidate answer to history
    session.conversation_history.append(ConversationTurn(
        role="CANDIDATE",
        type="TEXT",
        content=request.answer,
    ))

    # Policy matrix (no prior correctness for conversational — use last submission's
    last_correctness = True
    if session.submissions:
        last_eval = session.submissions[-1].evaluation or {}
        last_correctness = last_eval.get("correctness_passed", True)

    intent, legal_formats = select_intent_and_formats(
        time_remaining=request.time_remaining_seconds,
        min_time=min_time,
        correctness_passed=last_correctness,
        candidate_depth=None,
        difficulty=difficulty,
        turn_count=session.turn_count,
    )

    # Build messages
    active_fu = session.active_follow_up.model_dump() if session.active_follow_up else None
    system_prompt, user_message = interviewer.build_answer_messages(
        blueprint=blueprint,
        active_follow_up=active_fu,
        candidate_answer=request.answer,
        intent=intent,
        legal_formats=legal_formats,
        history=[t.model_dump() for t in session.conversation_history],
        time_remaining=request.time_remaining_seconds,
        difficulty=difficulty,
    )

    # LLM call
    raw = llm_client.complete_json(
        system_prompt=system_prompt,
        user_message=user_message,
        label=f"conv-eval:{request.session_id}",
    )
    output = ConversationalEvalOutput.model_validate(raw)

    # Reconcile
    force_close = intent == FollowUpIntent.CLOSE
    session, next_action = session_manager.reconcile_conversational_answer(
        session=session,
        output=output,
        intent=intent,
        force_close=force_close,
        blueprint=blueprint,
        time_remaining=request.time_remaining_seconds,
        min_time=min_time,
    )
    session_manager.persist(session)

    follow_up_view = output.follow_up.candidate_view() if output.follow_up and not session.closed else None

    return ConversationalAnswerResponse(
        session_id=session.session_id,
        stage=session.stage,
        evaluation=EvaluationBlock(
            finding=output.finding,
            answer_rating=output.answer_rating,
            follow_up=follow_up_view,
        ),
        candidate_depth=output.candidate_depth,
        next_action=next_action,
        closed=session.closed,
        report=session.report if session.closed else None,
    )
