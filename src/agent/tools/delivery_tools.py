from langchain_core.tools import tool

from src.db.repositories.learner_profile_repo import LearnerProfileRepo

_active_websockets: dict[str, list] = {}


def register_websocket(user_id: str, ws) -> None:
    if user_id not in _active_websockets:
        _active_websockets[user_id] = []
    _active_websockets[user_id].append(ws)


def unregister_websocket(user_id: str, ws) -> None:
    if user_id in _active_websockets:
        _active_websockets[user_id] = [
            w for w in _active_websockets[user_id] if w is not ws
        ]


@tool
async def deliver_intervention(
    user_id: str, intervention: dict, channel: str = "websocket"
) -> bool:
    """Push an intervention to the learner via WebSocket/SSE."""
    if channel == "websocket" and user_id in _active_websockets:
        for ws in _active_websockets[user_id]:
            try:
                await ws.send_json(intervention)
            except Exception:
                pass
        return True
    return False


@tool
async def log_intervention(
    user_id: str, intervention: dict, context: dict
) -> str:
    """Record an intervention for effectiveness tracking."""
    from src.db.repositories.intervention_repo import InterventionRepo

    repo = InterventionRepo()
    entry = await repo.create(
        user_id=user_id,
        session_id=context.get("session_id", ""),
        cycle_number=context.get("cycle_number", 0),
        diagnosed_concepts=context.get("diagnosed_concepts", []),
        intervention_type=intervention.get("type", "unknown"),
        intervention_data=intervention,
        engagement_score=context.get("engagement_score"),
        was_exploration=context.get("was_exploration", False),
    )
    return str(entry.id)
