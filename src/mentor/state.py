"""Single source of truth for one mentor cycle.

Uses Pydantic v2 for the per-stage payloads (so they can be JSON-
serialised into Redis) and a TypedDict for the LangGraph container.
The TypedDict inherits from MessagesState so the agent graph keeps the
operator.add reducer on `messages`.
"""

from __future__ import annotations

import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


# ───────────────────────── per-stage payloads ─────────────────────────


class PriorSnapshot(BaseModel):
    """Stage 1 output. Frozen baseline pulled from DB at cycle start."""

    user_id: UUID
    email: str = ""
    mastery_map: dict[str, dict[str, Any]] = Field(default_factory=dict)
    struggle_patterns: dict[str, Any] = Field(default_factory=dict)
    learning_style: dict[str, Any] = Field(default_factory=dict)
    prior_baseline: dict[str, Any] = Field(default_factory=dict)
    population_benchmarks: dict[str, dict[str, Any]] = Field(default_factory=dict)
    wisdom_rows: dict[str, dict[str, Any]] = Field(default_factory=dict)
    curriculum_progress: dict[str, Any] = Field(default_factory=dict)
    challenge_history: list[dict[str, Any]] = Field(default_factory=list)
    last_intervention: dict[str, Any] | None = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MentorEvent(BaseModel):
    """One observation line. Mirrors gui/utils/observation_logger.py."""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    session_id: str
    user_id: UUID
    event_type: Literal[
        "click",
        "page_view",
        "start_attempt",
        "end_attempt",
        "run_code",
        "submit_answer",
        "note_click",
    ]
    action: str
    page: str = "NA"
    page_id: str = "NA"
    challenge_id: str = "NA"
    slot_number: int | str = "NA"
    attempt_no: int | str = "NA"
    part_no: int | str = "NA"
    note_no: int | str = "NA"
    challenge_status: str = "NA"
    start_time: datetime | str = "NA"
    end_time: datetime | str = "NA"
    score: float | str = "NA"
    is_correct: bool | str = "NA"
    answer: str = "NA"
    code_path: str = "NA"
    run_no: int | str = "NA"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def numeric_score(self) -> float | None:
        if isinstance(self.score, (int, float)):
            return float(self.score)
        return None

    def is_correct_bool(self) -> bool | None:
        if isinstance(self.is_correct, bool):
            return self.is_correct
        return None


class ObservedSignals(BaseModel):
    """Stage 2 output. Aggregated signals from raw events."""

    events_count: int = 0
    events_by_type: dict[str, int] = Field(default_factory=dict)
    page_view_count: int = 0
    distinct_pages: set[str] = Field(default_factory=set)
    total_attempts: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    code_iterations: int = 0
    distinct_challenges: set[str] = Field(default_factory=set)
    slot_distribution: dict[str, int] = Field(default_factory=dict)
    last_event_at: datetime | None = None
    first_event_at: datetime | None = None
    session_duration_s: float = 0.0
    notes_clicked: int = 0
    submit_attempts: int = 0


class AnalyzedPattern(BaseModel):
    """Stage 3 output. Patterns + writeback audit trail."""

    struggling_concepts: list[str] = Field(default_factory=list)
    progressing_concepts: list[str] = Field(default_factory=list)
    abandoned_challenges: list[str] = Field(default_factory=list)
    hot_error_types: list[dict[str, Any]] = Field(default_factory=list)
    speed_signal: Literal["rushing", "deliberate", "normal"] = "normal"
    engagement_trend: Literal["improving", "stable", "declining"] = "stable"
    mastery_delta: dict[str, float] = Field(default_factory=dict)
    persisted_writes: list[dict[str, Any]] = Field(default_factory=list)


class InferredState(BaseModel):
    """Stage 4 output. LLM + memory inference."""

    confusion_level: float = 0.0
    clarity_level: float = 0.0
    inferred_weaknesses: list[dict[str, Any]] = Field(default_factory=list)
    inferred_strengths: list[dict[str, Any]] = Field(default_factory=list)
    memory_alignments: list[str] = Field(default_factory=list)
    memory_conflicts: list[str] = Field(default_factory=list)
    raw_diagnosis: str = ""


class InterpretedState(BaseModel):
    """Stage 5 output. Cross-verified inference."""

    severity: Literal["none", "low", "medium", "high"] = "none"
    confirmed_struggles: list[str] = Field(default_factory=list)
    rejected_weaknesses: list[str] = Field(default_factory=list)
    score_evidence: dict[str, list[float]] = Field(default_factory=dict)
    trend_evidence: dict[str, str] = Field(default_factory=dict)
    cross_check_notes: list[str] = Field(default_factory=list)


class InterventionDecision(BaseModel):
    """Stage 6 output."""

    intervention_id: UUID = Field(default_factory=uuid4)
    intervention_type: str
    target_concept: str
    rationale: str = ""
    priority: Literal["low", "medium", "high"] = "low"
    channel: Literal["websocket", "sse", "in_page"] = "websocket"
    content: dict[str, Any] = Field(default_factory=dict)
    requires_human_approval: bool = False
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    thompson_samples: dict[str, float] = Field(default_factory=dict)
    exploration: bool = False


class DeliveredIntervention(BaseModel):
    """Stage 7 output."""

    intervention_id: UUID
    delivered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    channel: str
    receipt: dict[str, Any] = Field(default_factory=dict)


class FeedbackRecord(BaseModel):
    """Stage 8 output. Measured effect of the previous intervention."""

    previous_intervention_id: UUID | None = None
    score_before: float | None = None
    score_after: float | None = None
    score_delta: float | None = None
    effectiveness_label: Literal["positive", "neutral", "negative", "unknown"] = "unknown"
    wisdom_updates: list[dict[str, Any]] = Field(default_factory=list)
    user_progress_writes: list[dict[str, Any]] = Field(default_factory=list)
    measurement_window_s: float = 0.0
    next_review_at: datetime | None = None


# ───────────────────────── LangGraph container ─────────────────────────


class MentorState(MessagesState):
    """Single source of truth for one cycle."""

    cycle_id: UUID
    user_id: UUID
    session_id: str
    email: str
    cycle_started_at: datetime

    raw_events: list[dict[str, Any]]
    cycle_count: int
    max_cycles: int
    should_pause: bool
    last_cycle_timestamp: str

    prior: dict[str, Any]
    observed: dict[str, Any]
    analyzed: dict[str, Any]
    inferred: dict[str, Any]
    interpreted: dict[str, Any]
    decision: dict[str, Any] | None
    delivered: dict[str, Any] | None
    feedback: dict[str, Any]

    needs_human_approval: bool
    pending_approval: dict[str, Any] | None

    messages: Annotated[list, operator.add]


def _to_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def create_initial_state(
    user_id: str | UUID,
    session_id: str,
    email: str = "",
    max_cycles: int = 5,
) -> dict[str, Any]:
    """Build a fresh state with empty stage payloads."""
    uid = _to_uuid(user_id)
    return {
        "cycle_id": uuid4(),
        "user_id": uid,
        "session_id": session_id,
        "email": email,
        "cycle_started_at": datetime.now(timezone.utc),
        "raw_events": [],
        "cycle_count": 0,
        "max_cycles": max_cycles,
        "should_pause": False,
        "last_cycle_timestamp": "",
        "prior": PriorSnapshot(user_id=uid, email=email).model_dump(mode="json"),
        "observed": ObservedSignals().model_dump(mode="json"),
        "analyzed": AnalyzedPattern().model_dump(mode="json"),
        "inferred": InferredState().model_dump(mode="json"),
        "interpreted": InterpretedState().model_dump(mode="json"),
        "decision": None,
        "delivered": None,
        "feedback": FeedbackRecord().model_dump(mode="json"),
        "needs_human_approval": False,
        "pending_approval": None,
        "messages": [],
    }
