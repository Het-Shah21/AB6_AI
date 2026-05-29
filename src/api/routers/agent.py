import logging
from typing import Any

from fastapi import APIRouter, Depends

from src.agent.graph import (
    compile_ooda_agent,
    create_initial_state,
)
from src.api.dependencies import get_session_cache
from src.memory.session_cache import SessionCache

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])


@router.post("/agent/sessions/{user_id}/start")
async def start_agent_session(
    user_id: str,
    session_id: str = "",
    cache: SessionCache = Depends(get_session_cache),
):
    import uuid
    sid = session_id or str(uuid.uuid4())
    state = await create_initial_state(user_id, sid)
    await cache.set_state(user_id, state)
    return {
        "status": "started",
        "user_id": user_id,
        "session_id": sid,
    }


@router.post("/agent/sessions/{user_id}/cycle")
async def run_ooda_cycle(
    user_id: str,
    cache: SessionCache = Depends(get_session_cache),
):
    state = await cache.get_state(user_id)
    if state is None:
        return {
            "status": "error",
            "message": "No active session. Start one first.",
        }

    agent = await compile_ooda_agent()
    events = await cache.pop_events(user_id)
    state["raw_events"] = state.get("raw_events", []) + events

    result = await agent.ainvoke(state)

    await cache.set_state(user_id, result)
    intervention = result.get("intervention_delivered")
    return {
        "status": "completed",
        "cycle": result.get("cycle_count", 0),
        "intervention": intervention,
        "diagnosis": result.get("diagnosed_struggles", []),
        "engagement": result.get("engagement_score", 0.5),
    }


@router.post("/agent/sessions/{user_id}/stop")
async def stop_agent_session(
    user_id: str,
    cache: SessionCache = Depends(get_session_cache),
):
    await cache.clear_session(user_id)
    return {"status": "stopped", "user_id": user_id}


@router.get("/agent/sessions/{user_id}/state")
async def get_agent_state(
    user_id: str,
    cache: SessionCache = Depends(get_session_cache),
):
    state = await cache.get_state(user_id)
    if state is None:
        return {"status": "no_active_session"}
    return {
        "status": "active",
        "user_id": user_id,
        "cycle_count": state.get("cycle_count", 0),
        "engagement_score": state.get("engagement_score", 0.5),
        "diagnosed_struggles": state.get("diagnosed_struggles", []),
        "last_intervention": state.get("intervention_delivered"),
    }
