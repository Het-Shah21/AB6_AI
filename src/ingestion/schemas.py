from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime


class ObservationEventPayload(BaseModel):
    user_id: str
    session_id: str
    event_type: str = Field(
        pattern=r"^(click|page_view|start_attempt|end_attempt|run_code|submit_answer|note_click)$"
    )
    action: str
    page: str = ""
    challenge_id: str = ""
    score: float | None = None
    is_correct: bool | None = None
    metadata: dict[str, Any] = {}
    timestamp: str = ""


class TelemetryEventPayload(BaseModel):
    user_id: str
    session_id: str
    joint_angles: list[float] = []
    imu_data: dict[str, float] = {}
    encoder_data: list[float] = []
    timestamp: str = ""


class DomainEventPayload(BaseModel):
    event_name: str
    user_id: str
    payload: dict[str, Any] = {}
    timestamp: str = ""


class BatchObservationPayload(BaseModel):
    events: list[ObservationEventPayload]


STREAMS = {
    "ai:observations": "ooda_observers",
    "ai:telemetry": "telemetry_agg",
    "ai:domain_events": "domain_processors",
}
