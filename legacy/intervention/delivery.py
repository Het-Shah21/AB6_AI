import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import WebSocket
from sse_starlette.sse import EventSourceResponse

from src.db.repositories.intervention_repo import InterventionRepo
from legacy.memory.session_cache import SessionCache

logger = logging.getLogger(__name__)

_active_connections: dict[str, list[WebSocket]] = {}


async def connect_websocket(user_id: str, ws: WebSocket) -> None:
    await ws.accept()
    if user_id not in _active_connections:
        _active_connections[user_id] = []
    _active_connections[user_id].append(ws)
    logger.info("WebSocket connected: user=%s", user_id)


async def disconnect_websocket(user_id: str, ws: WebSocket) -> None:
    if user_id in _active_connections:
        _active_connections[user_id] = [
            w for w in _active_connections[user_id] if w is not ws
        ]
        if not _active_connections[user_id]:
            del _active_connections[user_id]
    logger.info("WebSocket disconnected: user=%s", user_id)


async def deliver_via_websocket(
    user_id: str, intervention: dict[str, Any]
) -> bool:
    if user_id not in _active_connections:
        logger.warning(
            "No active WebSocket for user=%s", user_id
        )
        return False
    delivered = False
    for ws in _active_connections[user_id]:
        try:
            await ws.send_json(intervention)
            delivered = True
        except Exception as e:
            logger.error("WS send failed for user=%s: %s", user_id, e)
    return delivered


async def deliver_via_sse(
    user_id: str, intervention: dict[str, Any]
) -> dict[str, Any]:
    return {
        "event": "intervention",
        "data": json.dumps(intervention, default=str),
    }


async def deliver_intervention(
    user_id: str,
    intervention: dict[str, Any],
    channel: str = "websocket",
) -> bool:
    if channel == "websocket":
        return await deliver_via_websocket(user_id, intervention)
    return False
