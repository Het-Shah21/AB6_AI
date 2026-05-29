import operator
from typing import Annotated, Any

from langgraph.graph import MessagesState


class OODAState(MessagesState):
    user_id: str
    session_id: str

    raw_events: list[dict[str, Any]]
    telemetry_window: dict[str, Any]

    learner_profile: dict[str, Any]
    concept_state: dict[str, Any]
    diagnosed_struggles: list[str]
    engagement_score: float

    selected_intervention: dict[str, Any] | None
    intervention_candidates: list[dict[str, Any]]
    exploration_flag: bool

    intervention_delivered: dict[str, Any] | None
    delivery_channel: str

    cycle_count: int
    last_cycle_timestamp: str
    should_pause: bool
    max_cycles: int

    messages: Annotated[list, operator.add]
