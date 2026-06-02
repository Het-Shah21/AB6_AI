"""FastAPI entry point for the unified mentor.

This replaces `youtube_app.py` and the OODA routers. The legacy files
are kept for reference under `src/agent/` and `src/youtube_agent/`.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text

from src.config.settings import get_settings
from src.db.engine import get_session
from src.llm.sanitizer import sanitize_pii
from src.mentor.graph import get_compiled_graph
from src.mentor.memory.observation_log import ObservationLogService
from src.mentor.memory.session import MentorSessionCache
from src.mentor.observability import configure_logging, get_logger, set_cycle
from src.mentor.schemas import (
    ApprovalRequest,
    ApprovalResponse,
    CycleRequest,
    CycleResponse,
)
from src.mentor.state import MentorEvent, create_initial_state

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    obs = ObservationLogService()
    try:
        await obs.ensure_table()
        logger.info("mentor.observation_log.ready")
    except Exception as exc:
        logger.warning("mentor.observation_log.bootstrap failed: %s", exc)
    yield


app = FastAPI(
    title="AB6 AI Mentor",
    description="Unified 8-stage mentor replacing the OODA + YouTube agents.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Cycle lifecycle
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# UI support endpoints
# ---------------------------------------------------------------------------


async def _add_pending(user_id: uuid.UUID, cycle_id: uuid.UUID) -> None:
    cache = MentorSessionCache()
    r = await cache._get_redis()  # type: ignore[attr-defined]
    await r.sadd(f"mentor:pending:{user_id}", str(cycle_id))
    await r.expire(f"mentor:pending:{user_id}", 86400)
    payload = {
        "cycle_id": str(cycle_id),
        "queued_at": _utcnow_iso(),
    }
    await r.hset(
        f"mentor:pending:detail:{cycle_id}",
        mapping={**payload, "user_id": str(user_id)},
    )
    await r.expire(f"mentor:pending:detail:{cycle_id}", 86400)


async def _remove_pending(user_id: uuid.UUID, cycle_id: uuid.UUID) -> None:
    cache = MentorSessionCache()
    r = await cache._get_redis()  # type: ignore[attr-defined]
    await r.srem(f"mentor:pending:{user_id}", str(cycle_id))
    await r.delete(f"mentor:pending:detail:{cycle_id}")


def _utcnow_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@app.get("/mentor/users")
async def list_users(limit: int = 20) -> dict:
    sess = await get_session()
    try:
        result = await sess.execute(
            text(
                """
                SELECT id, email, full_name, organization, is_admin
                FROM ab6_user_data.user_details
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        users = [
            {
                "id": str(r[0]),
                "email": r[1],
                "full_name": r[2],
                "organization": r[3],
                "is_admin": r[4],
            }
            for r in result
        ]
    except Exception as exc:
        return {"users": [], "warning": f"user lookup failed: {exc}"}
    finally:
        await sess.close()
    return {"users": users}


@app.get("/mentor/pending/{user_id}")
async def list_pending(user_id: uuid.UUID) -> dict:
    cache = MentorSessionCache()
    r = await cache._get_redis()  # type: ignore[attr-defined]
    cycle_ids = await r.smembers(f"mentor:pending:{user_id}")
    out: list[dict] = []
    for cid in cycle_ids:
        detail = await r.hgetall(f"mentor:pending:detail:{cid}")
        if detail:
            out.append(detail)
        else:
            out.append({"cycle_id": cid, "user_id": str(user_id)})
    return {"pending": out}


@app.get("/mentor/history/{user_id}")
async def user_history(user_id: uuid.UUID, limit: int = 20) -> dict:
    sess = await get_session()
    try:
        cycles = await sess.execute(
            text(
                """
                SELECT cycle_id, occurred_at, event_type, challenge_id,
                       score, is_correct, action
                FROM ab6_learning_data.mentor_observation_log
                WHERE user_id = :uid
                ORDER BY occurred_at DESC
                LIMIT :limit
                """
            ),
            {"uid": str(user_id), "limit": limit},
        )
        rows = [
            {
                "cycle_id": str(r[0]) if r[0] else None,
                "occurred_at": r[1].isoformat() if r[1] else None,
                "event_type": r[2],
                "challenge_id": r[3],
                "score": float(r[4]) if r[4] is not None else None,
                "is_correct": r[5],
                "action": r[6],
            }
            for r in cycles
        ]
    except Exception as exc:
        return {"cycles": [], "warning": f"history lookup failed: {exc}"}
    finally:
        await sess.close()
    return {"cycles": rows}


# ---------------------------------------------------------------------------
# Cycle lifecycle
# ---------------------------------------------------------------------------


@app.post("/mentor/cycle", response_model=CycleResponse)
async def run_cycle(request: CycleRequest) -> CycleResponse:
    if request.cycle_id is None:
        request.cycle_id = uuid.uuid4()
    set_cycle(str(request.cycle_id), str(request.user_id))

    for ev in request.events:
        try:
            sanitized = sanitize_pii(ev.model_dump(mode="json"))
        except Exception:
            sanitized = ev.model_dump(mode="json")
        await MentorSessionCache().append_event(
            str(request.user_id), sanitized
        )
        try:
            obs = ObservationLogService()
            await obs.append(MentorEvent.model_validate(sanitized), request.cycle_id)
        except Exception as exc:
            logger.warning("observation_log.append failed: %s", exc)

    state = create_initial_state(
        user_id=str(request.user_id),
        session_id=request.session_id,
        cycle_id=request.cycle_id,
    )

    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": str(request.cycle_id)}}
    result = await graph.ainvoke(state, config=config)

    if result.get("intervention", {}).get("requires_approval"):
        await _add_pending(request.user_id, request.cycle_id)

    feedback = result.get("feedback") or {}
    intervention = result.get("intervention") or {}
    delivered = result.get("delivered") or {}

    return CycleResponse(
        cycle_id=request.cycle_id,
        user_id=request.user_id,
        status=str(feedback.get("success", "completed")),
        chosen_action=intervention.get("action"),
        rationale=intervention.get("rationale"),
        content=delivered.get("content"),
        delivered=bool(delivered.get("delivered", False)),
        requires_approval=bool(intervention.get("requires_approval", False)),
        confidence=intervention.get("confidence"),
        stage_history=result.get("stage_history", []),
    )


@app.post("/mentor/approve", response_model=ApprovalResponse)
async def resume_with_approval(request: ApprovalRequest) -> ApprovalResponse:
    from langgraph.types import Command

    set_cycle(str(request.cycle_id), str(request.user_id))
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": str(request.cycle_id)}}
    try:
        result = await graph.ainvoke(
            Command(
                resume={
                    "approved": request.approved,
                    "reviewer": request.reviewer,
                    "notes": request.notes,
                }
            ),
            config=config,
        )
    except Exception as exc:
        logger.exception("resume failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"resume failed: {exc}",
        ) from exc

    delivered = result.get("delivered") or {}
    await _remove_pending(request.user_id, request.cycle_id)
    return ApprovalResponse(
        cycle_id=request.cycle_id,
        approved=request.approved,
        delivered=bool(delivered.get("delivered", False)),
        content=delivered.get("content"),
        blocked_by=delivered.get("blocked_by"),
    )


# ---------------------------------------------------------------------------
# WebSocket — pushes intervention content in real time
# ---------------------------------------------------------------------------


@app.websocket("/mentor/ws")
async def ws_endpoint(ws: WebSocket, user_id: str) -> None:
    await ws.accept()
    cache = MentorSessionCache()
    try:
        while True:
            msg = await ws.receive_text()
            try:
                payload = json.loads(msg)
            except json.JSONDecodeError:
                await ws.send_json({"error": "invalid json"})
                continue
            ev = MentorEvent.model_validate(payload)
            await cache.append_event(user_id, ev.model_dump(mode="json"))
            await ws.send_json({"ack": ev.event_id, "buffered": True})
    except WebSocketDisconnect:
        logger.info("ws disconnect user=%s", user_id)


# ---------------------------------------------------------------------------
# Minimal static pages so the docker stack has a UI even without the
# AB6 frontend. Real product uses the AB6 frontend over `/mentor/cycle`.
# ---------------------------------------------------------------------------


_INDEX_HTML = """<!doctype html>
<html><head><title>AB6 AI Mentor</title></head>
<body>
<h1>AB6 AI Mentor</h1>
<p>Unified 8-stage mentor. Use POST <code>/mentor/cycle</code>.</p>
<p>WS: <code>/mentor/ws?user_id=&lt;uuid&gt;</code></p>
</body></html>
"""


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(_INDEX_HTML)


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    return "ok"


@app.get("/readyz", response_class=PlainTextResponse)
async def readyz() -> str:
    try:
        sess = await get_session()
        await sess.execute(text("SELECT 1"))
        await sess.close()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"db not ready: {exc}",
        )
    return "ready"
