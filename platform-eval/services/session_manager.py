"""
Session manager — THE single authority  # noqa: E402 for time gate, stage transitions,
policy-matrix selection, weighted score aggregation, and close decisions.
The LLM never emits finalScore.
"""
from __future__ import annotations
import time
import uuid
from models.dtos import (
    SessionState, Stage, NextAction, EvalReport, DimensionResult, PaceBlock,
    FollowUp, FollowUpIntent, CandidateDepth, CodeEvalOutput, ConversationalEvalOutput,
    SubmissionRecord, ConversationTurn,
)
from config.score_profiles import get_profile
from services.steering import select_intent_and_formats, MAX_TURNS
from infrastructure.store import session_store
from infrastructure.logger import log


class SessionManager:

    # ── Load / Create ──────────────────────────────────────────────────────────

    def load_or_create(self, session_id: str, problem_id: str) -> SessionState:
        raw = session_store.load(session_id)
        if raw:
            return SessionState.model_validate(raw)
        session = SessionState(
            session_id=session_id,
            problem_id=problem_id,
            start_time_seconds=int(time.time()),
        )
        self._persist(session)
        return session

    # ── Time Gate ─────────────────────────────────────────────────────────────

    def is_gate_fired(self, time_remaining: int, min_time: int) -> bool:
        """True → FORCE_CLOSE (no LLM call, still return correctness/efficiency feedback)."""
        return time_remaining <= min_time

    # ── Matrix Selection ──────────────────────────────────────────────────────

    def select_next_move(
        self,
        session: SessionState,
        time_remaining: int,
        min_time: int,
        correctness_passed: bool,
        depth: CandidateDepth | None,
    ):
        difficulty = "MEDIUM"  # overridden by blueprint in eval_core if available
        return select_intent_and_formats(
            time_remaining=time_remaining,
            min_time=min_time,
            correctness_passed=correctness_passed,
            candidate_depth=depth,
            difficulty=difficulty,
            turn_count=session.turn_count,
        )

    # ── Reconcile after LLM call ──────────────────────────────────────────────

    def reconcile_code_submission(
        self,
        session: SessionState,
        output: CodeEvalOutput,
        intent: FollowUpIntent,
        force_close: bool,
        blueprint: dict,
        time_remaining: int,
        min_time: int,
    ) -> tuple[SessionState, NextAction]:
        """Apply the code submission evaluation to the session, decide next action."""
        difficulty = blueprint.get("task", {}).get("difficulty", "MEDIUM").upper()

        # Record correctness/efficiency ratings for scoring
        record = SubmissionRecord(
            stage=session.stage.value,
            changed_files={},
            evaluation={
                "correctness_rating": output.correctness.rating,
                "efficiency_rating": output.efficiency.rating,
                "correctness_passed": output.correctness.passed,
                "efficiency_passed": output.efficiency.passed,
            },
        )
        session.submissions.append(record)

        # Append interviewer turn to history
        if output.follow_up and not force_close:
            session.conversation_history.append(ConversationTurn(
                role="INTERVIEWER",
                type=output.follow_up.type.value,
                content=output.follow_up.question,
            ))

        # Determine close
        should_close = (
            force_close
            or intent == FollowUpIntent.CLOSE
            or output.follow_up is None
        )

        if should_close:
            report = self._compute_report(session, output, blueprint, time_remaining, gate_fired=force_close)
            session.report = report
            session.closed = True
            session.stage = Stage.INITIAL_SUBMISSION
            return session, NextAction.CLOSE

        # Set up follow-up
        follow_up = output.follow_up
        follow_up_id = str(uuid.uuid4())
        session.active_follow_up_id = follow_up_id
        session.active_follow_up = follow_up
        session.turn_count += 1

        if follow_up.type.value == "IMPLEMENTATION":
            session.stage = Stage.FOLLOWUP_IMPLEMENTATION
            next_action = NextAction.AWAIT_SUBMISSION
        else:
            session.stage = Stage.FOLLOWUP_CONVERSATIONAL
            next_action = NextAction.AWAIT_ANSWER

        return session, next_action

    def reconcile_conversational_answer(
        self,
        session: SessionState,
        output: ConversationalEvalOutput,
        intent: FollowUpIntent,
        force_close: bool,
        blueprint: dict,
        time_remaining: int,
        min_time: int,
    ) -> tuple[SessionState, NextAction]:
        """Apply the conversational answer evaluation, decide next action."""
        # Record answer rating
        session.answer_ratings.append(output.answer_rating)

        # Append candidate turn (already in history from caller, just add interviewer)
        if output.follow_up and not force_close:
            session.conversation_history.append(ConversationTurn(
                role="INTERVIEWER",
                type=output.follow_up.type.value,
                content=output.follow_up.question,
            ))

        # Determine close
        should_close = (
            force_close
            or output.candidate_depth == CandidateDepth.STRONG
            or intent == FollowUpIntent.CLOSE
            or session.turn_count >= MAX_TURNS
            or output.follow_up is None
        )

        if should_close:
            report = self._compute_report(session, None, blueprint, time_remaining, gate_fired=force_close, conversational_output=output)
            session.report = report
            session.closed = True
            return session, NextAction.CLOSE

        follow_up = output.follow_up
        session.active_follow_up_id = str(uuid.uuid4())
        session.active_follow_up = follow_up
        session.turn_count += 1

        if follow_up.type.value == "IMPLEMENTATION":
            session.stage = Stage.FOLLOWUP_IMPLEMENTATION
            next_action = NextAction.AWAIT_SUBMISSION
        else:
            session.stage = Stage.FOLLOWUP_CONVERSATIONAL
            next_action = NextAction.AWAIT_ANSWER

        return session, next_action

    def close_without_llm(
        self, session: SessionState, blueprint: dict, time_remaining: int
    ) -> tuple[SessionState, NextAction]:
        """Force-close (time gate fired before LLM call) with no new evaluation."""
        report = self._compute_report(session, None, blueprint, time_remaining, gate_fired=True)
        session.report = report
        session.closed = True
        return session, NextAction.CLOSE

    # ── Weighted Score ────────────────────────────────────────────────────────

    def _compute_report(
        self,
        session: SessionState,
        code_output: CodeEvalOutput | None,
        blueprint: dict,
        time_remaining: int,
        gate_fired: bool,
        conversational_output: ConversationalEvalOutput | None = None,
    ) -> EvalReport:
        difficulty = blueprint.get("task", {}).get("difficulty", "MEDIUM").upper()
        profile = get_profile(difficulty)

        dimensions: dict[str, DimensionResult] = {}

        # Correctness & Efficiency — from most recent code submission
        correctness_rating = 5
        efficiency_rating = 5
        correctness_finding = "Not evaluated."
        efficiency_finding = "Not evaluated."

        if code_output:
            correctness_rating = code_output.correctness.rating
            efficiency_rating = code_output.efficiency.rating
            correctness_finding = code_output.correctness.finding
            efficiency_finding = code_output.efficiency.finding
        elif session.submissions:
            last = session.submissions[-1].evaluation or {}
            correctness_rating = last.get("correctness_rating", 5)
            efficiency_rating = last.get("efficiency_rating", 5)

        if "correctness" in profile:
            dimensions["correctness"] = DimensionResult(
                rating=correctness_rating,
                weight=profile["correctness"],
                finding=correctness_finding,
            )
        if "efficiency" in profile:
            dimensions["efficiency"] = DimensionResult(
                rating=efficiency_rating,
                weight=profile["efficiency"],
                finding=efficiency_finding,
            )

        # Follow-up — mean of answer ratings
        if "followUp" in profile:
            fu_rating = (
                round(sum(session.answer_ratings) / len(session.answer_ratings))
                if session.answer_ratings
                else 5
            )
            fu_finding = (
                conversational_output.finding
                if conversational_output
                else "Follow-up not conducted."
            )
            dimensions["followUp"] = DimensionResult(
                rating=fu_rating,
                weight=profile["followUp"],
                finding=fu_finding,
            )

        # Communication / designJudgment — from communication_finding if available
        comm_key = "designJudgment" if "designJudgment" in profile else "communication"
        if comm_key in profile:
            comm_finding = (
                (code_output.communication_finding if code_output else None)
                or (conversational_output.communication_finding if conversational_output else None)
                or "Not rated."
            )
            dimensions[comm_key] = DimensionResult(
                rating=6,  # neutral default; ideally rated by LLM at close
                weight=profile[comm_key],
                finding=comm_finding,
            )

        # Deterministic weighted score (model never sees this)
        total_weight = sum(d.weight for d in dimensions.values())
        if total_weight > 0:
            weighted_sum = sum(
                (d.rating / 10 * 100) * d.weight for d in dimensions.values()
            )
            final_score = round(weighted_sum / total_weight)
        else:
            final_score = 50

        elapsed = int(time.time()) - (session.start_time_seconds or int(time.time()))

        return EvalReport(
            final_score=final_score,
            weight_profile=difficulty,
            dimensions=dimensions,
            pace=PaceBlock(
                turns_used=session.turn_count,
                time_consumed_seconds=elapsed,
                gate_fired=gate_fired,
            ),
        )

    # ── Persist ───────────────────────────────────────────────────────────────

    def _persist(self, session: SessionState) -> None:
        session_store.save(session.session_id, session.model_dump())

    def persist(self, session: SessionState) -> None:
        self._persist(session)


session_manager = SessionManager()
