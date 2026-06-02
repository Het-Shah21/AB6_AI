import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from legacy.api.dependencies import get_stream_consumer
from legacy.ingestion.consumer import RedisStreamConsumer
from legacy.ingestion.schemas import TelemetryEventPayload

logger = logging.getLogger(__name__)
router = APIRouter(tags=["telemetry"])


@router.websocket("/telemetry/ws")
async def telemetry_websocket(
    websocket: WebSocket,
    consumer: RedisStreamConsumer = Depends(get_stream_consumer),
):
    await websocket.accept()
    logger.info("Telemetry WebSocket connected")

    try:
        while True:
            data = await websocket.receive_json()
            event = TelemetryEventPayload(**data)
            msg_id = await consumer.push_telemetry(event.model_dump())
            await websocket.send_json({
                "status": "ok",
                "message_id": msg_id,
            })
    except WebSocketDisconnect:
        logger.info("Telemetry WebSocket disconnected")
    except Exception as e:
        logger.error("Telemetry WebSocket error: %s", e)
