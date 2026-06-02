"""Observation log — append-only mirror of every MentorEvent the
mentor processes.  Backed by the active SQL backend
(``postgres``, ``sqlite`` or ``memory``); degrades to a no-op when the
table is missing.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from src.db.engine import backend_name, get_session
from src.mentor.observability import get_logger, log_event
from src.mentor.state import MentorEvent

logger = get_logger(__name__)


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, default=str)


class ObservationLogService:
    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    async def _get_session(self):
        if self._session is not None:
            return self._session
        return await get_session()

    async def ensure_table(self) -> None:
        """Idempotent CREATE TABLE.  Cheap on all backends."""
        try:
            sess = await self._get_session()
            await sess.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS ab6_learning_data.mentor_observation_log (
                        id            TEXT PRIMARY KEY,
                        event_id      TEXT,
                        user_id       TEXT,
                        session_id    TEXT,
                        cycle_id      TEXT,
                        received_at   TEXT,
                        occurred_at   TEXT,
                        event_type    TEXT,
                        page          TEXT,
                        page_id       TEXT,
                        challenge_id  TEXT,
                        slot_number   INTEGER,
                        attempt_no    INTEGER,
                        part_no       INTEGER,
                        note_no       INTEGER,
                        challenge_status TEXT,
                        start_time    TEXT,
                        end_time      TEXT,
                        score         REAL,
                        is_correct    INTEGER,
                        answer        TEXT,
                        code_path     TEXT,
                        run_no        INTEGER,
                        action        TEXT,
                        metadata      TEXT
                    )
                    """
                )
            )
        except Exception as exc:
            logger.warning("observation_log.ensure_table failed: %s", exc)

    async def append(self, event: MentorEvent, cycle_id: uuid.UUID) -> str:
        try:
            sess = await self._get_session()
            row_id = str(uuid.uuid4())
            meta = event.metadata or {}
            await sess.execute(
                text(
                    """
                    INSERT INTO ab6_learning_data.mentor_observation_log (
                        id, event_id, user_id, session_id, cycle_id, occurred_at,
                        event_type, page, page_id, challenge_id, slot_number,
                        attempt_no, part_no, note_no, challenge_status,
                        start_time, end_time, score, is_correct, answer,
                        code_path, run_no, action, metadata
                    ) VALUES (
                        :id, :event_id, :user_id, :session_id, :cycle_id,
                        :occurred_at, :event_type, :page, :page_id,
                        :challenge_id, :slot_number, :attempt_no, :part_no,
                        :note_no, :challenge_status, :start_time, :end_time,
                        :score, :is_correct, :answer, :code_path, :run_no,
                        :action, :meta
                    )
                    """
                ),
                {
                    "id": row_id,
                    "event_id": event.event_id,
                    "user_id": str(event.user_id) if event.user_id else None,
                    "session_id": event.session_id,
                    "cycle_id": str(cycle_id),
                    "occurred_at": str(event.timestamp) if event.timestamp else None,
                    "event_type": event.event_type,
                    "page": event.page,
                    "page_id": event.page_id,
                    "challenge_id": event.challenge_id,
                    "slot_number": event.slot_number,
                    "attempt_no": event.attempt_no,
                    "part_no": event.part_no,
                    "note_no": event.note_no,
                    "challenge_status": event.challenge_status,
                    "start_time": str(event.start_time) if event.start_time else None,
                    "end_time": str(event.end_time) if event.end_time else None,
                    "score": event.score,
                    "is_correct": 1 if event.is_correct else (0 if event.is_correct is False else None),
                    "answer": event.answer,
                    "code_path": event.code_path,
                    "run_no": event.run_no,
                    "action": event.action,
                    "meta": _json_dumps(meta),
                },
            )
            log_event(
                logger,
                "observation.log.appended",
                event_id=event.event_id,
                cycle_id=str(cycle_id),
                event_type=event.event_type,
            )
            return row_id
        except Exception as exc:
            logger.warning("observation_log.append failed: %s", exc)
            return ""

    async def fetch_for_session(
        self,
        user_id: str | uuid.UUID,
        session_id: str,
        limit: int = 500,
    ) -> list[dict]:
        try:
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
            out: list[dict] = []
            for r in result:
                out.append(
                    {
                        "id": r[0],
                        "event_id": r[1],
                        "cycle_id": r[2],
                        "occurred_at": r[3],
                        "event_type": r[4],
                        "page": r[5],
                        "page_id": r[6],
                        "challenge_id": r[7],
                        "slot_number": r[8],
                        "attempt_no": r[9],
                        "part_no": r[10],
                        "note_no": r[11],
                        "challenge_status": r[12],
                        "start_time": r[13],
                        "end_time": r[14],
                        "score": float(r[15]) if r[15] is not None else None,
                        "is_correct": r[16],
                        "answer": r[17],
                        "code_path": r[18],
                        "run_no": r[19],
                        "action": r[20],
                        "metadata": json.loads(r[21]) if r[21] else {},
                    }
                )
            return out
        except Exception as exc:
            logger.warning("observation_log.fetch_for_session failed: %s", exc)
            return []
