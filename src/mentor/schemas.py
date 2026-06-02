"""Public schemas used by the mentor router and mentor_app.py."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class InterventionEnvelope(BaseModel):
    """Wire format for an intervention pushed over WS / SSE."""

    intervention_id: UUID
    user_id: UUID
    session_id: str
    type: str
    target_concept: str
    rationale: str = ""
    priority: str = "low"
    channel: str = "websocket"
    content: dict[str, Any] = Field(default_factory=dict)
    display: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    requires_human_approval: bool = False
    cycle_id: UUID | None = None
    delivered_at: datetime | None = None


class CycleRequest(BaseModel):
    user_id: UUID
    session_id: str
    raw_events: list[dict[str, Any]] = Field(default_factory=list)
    max_cycles: int = 5
    email: str = ""


class CycleResponse(BaseModel):
    cycle_id: UUID
    user_id: UUID
    session_id: str
    cycle_count: int
    severity: str
    confusion_level: float
    clarity_level: float
    confirmed_struggles: list[str]
    rejected_weaknesses: list[str]
    decision: dict[str, Any] | None
    delivered: dict[str, Any] | None
    feedback: dict[str, Any]
    needs_human_approval: bool
    messages: list[dict[str, Any]]


class ApprovalRequest(BaseModel):
    intervention_id: UUID
    approved: bool
    reviewer: str = "mentor-admin"
    note: str = ""


class ApprovalResponse(BaseModel):
    intervention_id: UUID
    approved: bool
    delivered: bool
    receipt: dict[str, Any] = Field(default_factory=dict)
