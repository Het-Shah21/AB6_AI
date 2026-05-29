from pydantic import BaseModel
from typing import Any
from datetime import datetime


class ObservationEvent(BaseModel):
    user_id: str
    session_id: str
    event_type: str
    action: str
    page: str = ""
    challenge_id: str = ""
    score: float | None = None
    is_correct: bool | None = None
    metadata: dict[str, Any] = {}
    timestamp: str = ""


class TelemetryEvent(BaseModel):
    user_id: str
    session_id: str
    joint_angles: list[float] = []
    imu_data: dict[str, float] = {}
    encoder_data: list[float] = []
    timestamp: str = ""


class DomainEvent(BaseModel):
    event_name: str
    user_id: str
    payload: dict[str, Any] = {}
    timestamp: str = ""


class InterventionEvent(BaseModel):
    intervention_id: str
    user_id: str
    session_id: str
    type: str
    content: dict[str, Any]
    display: dict[str, Any]
    metadata: dict[str, Any] = {}
    timestamp: str = ""
