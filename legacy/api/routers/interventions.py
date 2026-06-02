import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse

from legacy.intervention.delivery import (
    connect_websocket,
    disconnect_websocket,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["interventions"])


@router.websocket("/interventions/{user_id}/ws")
async def intervention_websocket(
    websocket: WebSocket,
    user_id: str,
):
    await connect_websocket(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await disconnect_websocket(user_id, websocket)
    except Exception as e:
        logger.error("Intervention WS error: %s", e)
        await disconnect_websocket(user_id, websocket)


@router.get("/interventions/{user_id}/stream")
async def intervention_sse(user_id: str):
    async def event_generator():
        yield {"event": "connected", "data": json.dumps({"user_id": user_id})}

    return EventSourceResponse(event_generator())
