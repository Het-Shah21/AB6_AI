import logging

from fastapi import APIRouter, Depends

from src.ingestion.consumer import RedisStreamConsumer
from src.ingestion.schemas import (
    ObservationEventPayload,
    BatchObservationPayload,
    DomainEventPayload,
)
from src.api.dependencies import get_stream_consumer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])


@router.post("/events")
async def ingest_observation(
    payload: ObservationEventPayload,
    consumer: RedisStreamConsumer = Depends(get_stream_consumer),
):
    msg_id = await consumer.push_observation(payload.model_dump())
    return {"status": "ok", "message_id": msg_id}


@router.post("/events/batch")
async def ingest_observation_batch(
    payload: BatchObservationPayload,
    consumer: RedisStreamConsumer = Depends(get_stream_consumer),
):
    ids = []
    for event in payload.events:
        msg_id = await consumer.push_observation(event.model_dump())
        ids.append(msg_id)
    return {"status": "ok", "message_ids": ids, "count": len(ids)}


@router.post("/domain-events")
async def ingest_domain_event(
    payload: DomainEventPayload,
    consumer: RedisStreamConsumer = Depends(get_stream_consumer),
):
    msg_id = await consumer.push_domain_event(payload.model_dump())
    return {"status": "ok", "message_id": msg_id}
