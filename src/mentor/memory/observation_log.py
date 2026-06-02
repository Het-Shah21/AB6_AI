"""Persists raw MentorEvent lines to a Postgres table for replay/audit.

The mentor reads from the rich JSON-line event stream produced by the
AB6 frontend. We mirror the payload verbatim into `mentor_observation_log`
so cycles can be re-run offline against historical sessions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.mentor.observability import get_logger, log_event
from src.mentor.state import MentorEvent

logger = get_logger(__name__)


class ObservationLogService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return get_session()

    async def ensure_table(self) -> None:
        """Idempotent CREATE. Safe to call on startup."""
        sess = await self._get_session()
        await sess.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ab6_learning_data.mentor_observation_log (
                    id            UUID PRIMARY KEY,
                    event_id      TEXT,
                    user_id       UUID,
                    session_id    TEXT,
                    cycle_id      UUID,
                    received_at   TIMESTAMPTZ DEFAULT NOW(),
                    occurred_at   TIMESTAMPTZ,
                    event_type    TEXT,
                    page          TEXT,
                    page_id       TEXT,
                    challenge_id  TEXT,
                    slot_number   INT,
                    attempt_no    INT,
                    part_no       INT,
                    note_no       INT,
                    challenge_status TEXT,
                    start_time    TIMESTAMPTZ,
                    end_time      TIMESTAMPTZ,
                    score         NUMERIC,
                    is_correct    BOOLEAN,
                    answer        TEXT,
                    code_path     TEXT,
                    run_no        INT,
                    action        TEXT,
                    metadata      JSONB
                )
                """
            )
        )
        await sess.commit()

    async def append(self, event: MentorEvent, cycle_id: uuid.UUID) -> str:
        sess = await self._get_session()
        row_id = uuid.uuid4()
        meta = event.metadata or {}
        await sess.execute(
            text(
                """
                INSERT INTO ab6_learning_data.mentor_observation_log (
                    id, event_id, user_id, session_id, cycle_id, occurred_at,
                    event_type, page, page_id, challenge_id, slot_number,
                    attempt_no, part_no, note_no, challenge_status, start_time,
                    end_time, score, is_correct, answer, code_path, run_no,
                    action, metadata
                ) VALUES (
                    :id, :event_id, :user_id, :session_id, :cycle_id,
                    :occurred_at, :event_type, :page, :page_id, :challenge_id,
                    :slot_number, :attempt_no, :part_no, :note_no,
                    :challenge_status, :start_time, :end_time, :score,
                    :is_correct, :answer, :code_path, :run_no, :action,
                    CAST(:meta AS JSONB)
                )
                """
            ),
            {
                "id": str(row_id),
                "event_id": event.event_id,
                "user_id": str(event.user_id) if event.user_id else None,
                "session_id": event.session_id,
                "cycle_id": str(cycle_id),
                "occurred_at": event.timestamp,
                "event_type": event.event_type,
                "page": event.page,
                "page_id": event.page_id,
                "challenge_id": event.challenge_id,
                "slot_number": event.slot_number,
                "attempt_no": event.attempt_no,
                "part_no": event.part_no,
                "note_no": event.note_no,
                "challenge_status": event.challenge_status,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "score": event.score,
                "is_correct": event.is_correct,
                "answer": event.answer,
                "code_path": event.code_path,
                "run_no": event.run_no,
                "action": event.action,
                "meta": _json_dumps(meta),
            },
        )
        await sess.commit()
        log_event(
            logger,
            "observation.log.appended",
            event_id=event.event_id,
            cycle_id=str(cycle_id),
            event_type=event.event_type,
        )
        return str(row_id)

    async def fetch_for_session(
        self,
        user_id: str | uuid.UUID,
        session_id: str,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        sess = await self._get_session()
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        result = await sess.execute(
            text(
                """
                SELECT id, event_id, cycle_id, occurred_at, event_type, page,
                       page_id, challenge_id, slot_number, attempt_no, part_no,
                       note_no, challenge_status, start_time, end_time, score,
                       is_correct, answer, code_path, run_no, action, metadata
                FROM ab6_learning_data.mentor_observation_log
                WHERE user_id = :uid AND session_id = :sid
                ORDER BY occurred_at ASC
                LIMIT :limit
                """
            ),
            {"uid": str(uid), "sid": session_id, "limit": limit},
        )
        out: list[dict[str, Any]] = []
        for r in result:
            out.append(
                {
                    "id": str(r[0]),
                    "event_id": r[1],
                    "cycle_id": str(r[2]) if r[2] else None,
                    "occurred_at": r[3].isoformat() if r[3] else None,
                    "event_type": r[4],
                    "page": r[5],
                    "page_id": r[6],
                    "challenge_id": r[7],
                    "slot_number": r[8],
                    "attempt_no": r[9],
                    "part_no": r[10],
                    "note_no": r[11],
                    "challenge_status": r[12],
                    "start_time": r[13].isoformat() if r[13] else None,
                    "end_time": r[14].isoformat() if r[14] else None,
                    "score": float(r[15]) if r[15] is not None else None,
                    "is_correct": r[16],
                    "answer": r[17],
                    "code_path": r[18],
                    "run_no": r[19],
                    "action": r[20],
                    "metadata": r[21],
                }
            )
        return out


def _json_dumps(payload: Any) -> str:
    import json
    return json.dumps(payload, default=str)
