from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_serializer


# ── Enums ──────────────────────────────────────────────────────────────────────

class Stage(str, Enum):
    INITIAL_SUBMISSION = "INITIAL_SUBMISSION"
    FOLLOWUP_CONVERSATIONAL = "FOLLOWUP_CONVERSATIONAL"
    FOLLOWUP_IMPLEMENTATION = "FOLLOWUP_IMPLEMENTATION"


class NextAction(str, Enum):
    AWAIT_ANSWER = "AWAIT_ANSWER"
    AWAIT_SUBMISSION = "AWAIT_SUBMISSION"
    CLOSE = "CLOSE"


class FollowUpType(str, Enum):
    CONVERSATIONAL = "CONVERSATIONAL"
    IMPLEMENTATION = "IMPLEMENTATION"


class FollowUpFormat(str, Enum):
    TEXT = "TEXT"
    CODE = "CODE"
    MCQ = "MCQ"
    TRUE_FALSE = "TRUE_FALSE"
    COMPLEXITY = "COMPLEXITY"


class FollowUpIntent(str, Enum):
    ESCALATE = "ESCALATE"
    CONSOLIDATE = "CONSOLIDATE"
    QUICK_PROBE = "QUICK_PROBE"
    QUICK_CLOSE = "QUICK_CLOSE"
    CLOSE = "CLOSE"


class CandidateDepth(str, Enum):
    SHALLOW = "SHALLOW"
    ADEQUATE = "ADEQUATE"
    STRONG = "STRONG"


class InputType(str, Enum):
    CODE_SUBMISSION = "CODE_SUBMISSION"
    CONVERSATIONAL_ANSWER = "CONVERSATIONAL_ANSWER"


# ── Follow-up ──────────────────────────────────────────────────────────────────

class FollowUp(BaseModel):
    intent: FollowUpIntent
    type: FollowUpType
    format: FollowUpFormat
    question: str
    options: list[str] | None = None
    # server-only — excluded via candidate_view(); never sent to candidate
    expected_answer_key: str | None = None
    # tracks which blueprint focus area this question targets
    chosen_area: str | None = None

    def candidate_view(self) -> dict:
        return self.model_dump(exclude={"expected_answer_key", "chosen_area"})


# ── Score / Report ─────────────────────────────────────────────────────────────

class DimensionResult(BaseModel):
    rating: int
    weight: int
    finding: str


class PaceBlock(BaseModel):
    turns_used: int
    time_consumed_seconds: int
    gate_fired: bool


class EvalReport(BaseModel):
    final_score: int
    weight_profile: str
    dimensions: dict[str, DimensionResult]
    # per-concept breakdown from follow-up conversation
    concept_dimensions: dict[str, DimensionResult] = Field(default_factory=dict)
    pace: PaceBlock


# ── Session State ──────────────────────────────────────────────────────────────

class ConversationTurn(BaseModel):
    role: str  # INTERVIEWER | CANDIDATE
    type: str  # CODE | TEXT
    content: str


class SubmissionRecord(BaseModel):
    stage: str
    changed_files: dict[str, str]
    test_result: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None


class SessionState(BaseModel):
    session_id: str
    problem_id: str
    stage: Stage = Stage.INITIAL_SUBMISSION
    active_follow_up_id: str | None = None
    active_follow_up: FollowUp | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    submissions: list[SubmissionRecord] = Field(default_factory=list)
    answer_ratings: list[int] = Field(default_factory=list)
    turn_count: int = 0
    closed: bool = False
    report: EvalReport | None = None
    # concept tracking
    probed_areas: list[str] = Field(default_factory=list)
    concept_scores: dict[str, int] = Field(default_factory=dict)
    concept_findings: dict[str, str] = Field(default_factory=dict)
    # timing
    start_time_seconds: int | None = None
    time_consumed_seconds: int = 0


# ── LLM Structured-Output Schemas ─────────────────────────────────────────────

class CorrectnessRating(BaseModel):
    rating: int = Field(..., ge=1, le=10)
    passed: bool
    finding: str


class EfficiencyRating(BaseModel):
    rating: int = Field(..., ge=1, le=10)
    passed: bool
    finding: str


class CodeEvalOutput(BaseModel):
    """Schema the LLM fills for CODE_SUBMISSION — rates only, never scores."""
    # 1-3 sentences acknowledging the candidate's code before the follow-up question
    acknowledgment: str | None = None
    correctness: CorrectnessRating
    efficiency: EfficiencyRating
    follow_up: FollowUp | None = None
    communication_finding: str | None = None


class ConversationalEvalOutput(BaseModel):
    """Schema the LLM fills for CONVERSATIONAL_ANSWER — rates only."""
    # 1-3 sentences acknowledging the candidate's answer before the next question
    acknowledgment: str | None = None
    finding: str
    candidate_depth: CandidateDepth
    answer_rating: int = Field(..., ge=1, le=10)
    follow_up: FollowUp | None = None
    communication_finding: str | None = None


# ── Request DTOs ───────────────────────────────────────────────────────────────

class CodeSubmission(BaseModel):
    target_file: str | None = None
    changed_files: dict[str, str]
    # test_result intentionally omitted — eval is only invoked after all tests pass


class CodeSubmitRequest(BaseModel):
    problem_id: str
    session_id: str
    input_type: InputType = InputType.CODE_SUBMISSION
    submission: CodeSubmission
    gold_master_ref: str | None = None
    time_remaining_seconds: int = 3600
    minimum_time_remaining_seconds: int = 600
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class ConversationalAnswerRequest(BaseModel):
    problem_id: str
    session_id: str
    input_type: InputType = InputType.CONVERSATIONAL_ANSWER
    answer: str
    time_remaining_seconds: int = 3600
    minimum_time_remaining_seconds: int = 600
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


# ── Response DTOs ──────────────────────────────────────────────────────────────

class EvaluationBlock(BaseModel):
    # Interactive acknowledgment shown to candidate before the follow-up question
    acknowledgment: str | None = None
    correctness: CorrectnessRating | None = None
    efficiency: EfficiencyRating | None = None
    finding: str | None = None
    answer_rating: int | None = None
    follow_up: dict | None = None  # candidate view (no expected_answer_key or chosen_area)


class CodeSubmitResponse(BaseModel):
    session_id: str
    stage: Stage
    evaluation: EvaluationBlock
    candidate_depth: CandidateDepth | None = None
    next_action: NextAction
    closed: bool
    report: EvalReport | None = None


class ConversationalAnswerResponse(BaseModel):
    session_id: str
    stage: Stage
    evaluation: EvaluationBlock
    candidate_depth: CandidateDepth | None = None
    next_action: NextAction
    closed: bool
    report: EvalReport | None = None
