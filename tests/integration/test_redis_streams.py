import json
import pytest


@pytest.mark.asyncio
async def test_event_schema_validation():
    from src.ingestion.schemas import ObservationEventPayload

    valid = ObservationEventPayload(
        user_id="u1",
        session_id="s1",
        event_type="click",
        action="view",
        page="/challenge/1",
    )
    assert valid.event_type == "click"


@pytest.mark.asyncio
async def test_batch_observation_schema():
    from src.ingestion.schemas import BatchObservationPayload, ObservationEventPayload

    batch = BatchObservationPayload(
        events=[
            ObservationEventPayload(
                user_id="u1", session_id="s1", event_type="click", action="view"
            ),
            ObservationEventPayload(
                user_id="u1",
                session_id="s1",
                event_type="end_attempt",
                action="submit",
                challenge_id="c1",
                score=0.9,
                is_correct=True,
            ),
        ]
    )
    assert len(batch.events) == 2
