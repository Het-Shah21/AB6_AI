import logging
from typing import Any

from langgraph.graph import StateGraph, START, END

from legacy.agent.state import OODAState
from legacy.agent.nodes import (
    observe_node,
    orient_node,
    decide_node,
    decide_router,
    act_node,
    pause_node,
)
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_CHECKPOINTER = None


def _get_checkpointer():
    global _CHECKPOINTER
    if _CHECKPOINTER is not None:
        return _CHECKPOINTER
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        settings = get_settings()
        cp = AsyncPostgresSaver.from_conn_string(
            settings.database_url.replace("+asyncpg", "")
        )
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        _CHECKPOINTER = cp
    except Exception as e:
        logger.warning("Postgres checkpointer unavailable (%s), using MemorySaver fallback", e)
        from langgraph.checkpoint.memory import MemorySaver
        _CHECKPOINTER = MemorySaver()
    return _CHECKPOINTER


def continue_router(state: OODAState) -> str:
    max_cycles = state.get("max_cycles", 9999)
    current = state.get("cycle_count", 0)
    if current >= max_cycles:
        logger.info("Reached max_cycles=%d at cycle_count=%d, ending", max_cycles, current)
        return "end"
    return "orient"


def build_ooda_graph() -> StateGraph:
    builder = StateGraph(OODAState)

    builder.add_node("observe", observe_node)
    builder.add_node("orient", orient_node)
    builder.add_node("decide", decide_node)
    builder.add_node("act", act_node)
    builder.add_node("pause", pause_node)

    builder.add_edge(START, "observe")
    builder.add_conditional_edges("observe", continue_router, {"orient": "orient", "end": END})
    builder.add_edge("orient", "decide")
    builder.add_conditional_edges("decide", decide_router, ["act", "pause"])
    builder.add_edge("act", "observe")
    builder.add_edge("pause", "observe")

    return builder


async def compile_ooda_agent():
    builder = build_ooda_graph()
    checkpointer = _get_checkpointer()
    if hasattr(checkpointer, "setup"):
        try:
            await checkpointer.setup()
        except Exception:
            pass

    agent = builder.compile(checkpointer=checkpointer)
    logger.info("OODA agent compiled with checkpointer: %s", type(checkpointer).__name__)
    return agent


async def create_initial_state(
    user_id: str,
    session_id: str,
    max_cycles: int = 9999,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "session_id": session_id,
        "raw_events": [],
        "telemetry_window": {},
        "learner_profile": {},
        "concept_state": {},
        "diagnosed_struggles": [],
        "engagement_score": 0.5,
        "selected_intervention": None,
        "intervention_candidates": [],
        "exploration_flag": False,
        "intervention_delivered": None,
        "delivery_channel": "",
        "cycle_count": 0,
        "last_cycle_timestamp": "",
        "should_pause": False,
        "messages": [],
        "max_cycles": max_cycles,
    }
