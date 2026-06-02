"""In-memory database backend.

Mirrors the subset of the Postgres schema the mentor uses, stored as
plain Python data structures.  Used when ``MENTOR_BACKEND=memory``.

Public surface is the same as the SQLAlchemy ``AsyncSession`` the
Postgres path returns — ``execute(text(...))``, ``commit()``,
``close()`` — so callers don't have to branch.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from src.mentor.observability import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _Result:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def all(self) -> list[tuple]:
        return list(self._rows)

    def one_or_none(self) -> tuple | None:
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self) -> Any:
        return self._rows[0][0] if self._rows else None

    def scalars(self) -> "_ScalarResult":
        return _ScalarResult([r[0] if r else None for r in self._rows])


class _ScalarResult:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def all(self) -> list[Any]:
        return list(self._values)


class MemorySession:
    """In-process replacement for ``AsyncSession``.

    Stores rows in module-level dicts.  All public SQL goes through
    ``execute(text(...))`` so the mentor code can stay schema-agnostic.
    """

    # Module-level state, shared across all sessions in the process.
    _state: dict[str, list[dict]] = {
        "ab6_user_data.user_details": [],
        "ab6_learning_data.courses": [],
        "ab6_learning_data.challenges": [],
        "ab6_learning_data.user_progress": [],
        "ab6_learning_data.challenge_attempts": [],
        "ab6_learning_data.challenge_runs": [],
        "ab6_learning_data.challenge_submissions": [],
        "ab6_learning_data.challenge_videos": [],
        "ab6_learning_data.events": [],
        "ab6_learning_data.ai_concept_mappings": [],
        "ab6_learning_data.ai_learner_profile": [],
        "ab6_learning_data.ai_intervention_log": [],
        "ab6_learning_data.ai_population_benchmarks": [],
        "ab6_learning_data.ai_wisdom_store": [],
        "ab6_learning_data.mentor_observation_log": [],
    }
    _lock = asyncio.Lock()

    def __init__(self) -> None:
        self._pending_writes: list[tuple[str, dict]] = []
        self._seeded = False

    # ------------------------------------------------------------------
    # AsyncSession-compatible surface
    # ------------------------------------------------------------------

    async def execute(self, statement: Any, params: dict | None = None) -> _Result:
        text_sql = str(statement).strip().rstrip(";")
        params = params or {}
        await self._seed_if_needed()

        upper = text_sql.upper()
        async with self._lock:
            if upper.startswith("SELECT 1"):
                return _Result([(1,)])
            if upper.startswith("SELECT 1 AS DUAL"):
                return _Result([(1,)])

            if upper.startswith("INSERT"):
                await self._handle_insert(text_sql, params)
                return _Result([])
            if upper.startswith("UPDATE"):
                await self._handle_update(text_sql, params)
                return _Result([])
            if upper.startswith("DELETE"):
                await self._handle_delete(text_sql, params)
                return _Result([])
            if upper.startswith("CREATE TABLE"):
                return _Result([])
            if upper.startswith("SELECT"):
                rows = self._handle_select(text_sql, params)
                return _Result(rows)

        logger.warning("memory.execute: unhandled sql: %s", text_sql[:60])
        return _Result([])

    async def commit(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def refresh(self, instance: Any) -> None:
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _seed_if_needed(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        if not self._state["ab6_user_data.user_details"]:
            self._state["ab6_user_data.user_details"].extend(_seed_users())

    async def _handle_insert(self, sql: str, params: dict) -> None:
        target = _extract_target_table(sql)
        if target is None:
            return
        row = dict(params)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", _utcnow())
        if target in self._state:
            self._state[target].append(row)

    async def _handle_update(self, sql: str, params: dict) -> None:
        target = _extract_target_table(sql)
        if target is None or target not in self._state:
            return
        where = _extract_where(sql, params)
        for row in self._state[target]:
            if _row_matches(row, where):
                for k, v in params.items():
                    if not _is_where_key(k):
                        row[k] = v

    async def _handle_delete(self, sql: str, params: dict) -> None:
        target = _extract_target_table(sql)
        if target is None or target not in self._state:
            return
        where = _extract_where(sql, params)
        self._state[target] = [
            r for r in self._state[target] if not _row_matches(r, where)
        ]

    def _handle_select(self, sql: str, params: dict) -> list[tuple]:
        target = _extract_target_table(sql)
        if target is None or target not in self._state:
            return []
        where = _extract_where(sql, params)
        cols = _extract_select_columns(sql)
        out: list[tuple] = []
        for row in self._state[target]:
            if not _row_matches(row, where):
                continue
            if cols is None or cols == ["*"]:
                out.append(tuple(_ordered_values(row)))
            else:
                out.append(tuple(_coerce(row.get(c)) for c in cols))
        return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_target_table(sql: str) -> str | None:
    upper = sql.upper()
    for kw in ("INSERT INTO", "UPDATE", "DELETE FROM", "FROM", "JOIN", "INTO"):
        idx = upper.find(kw + " ")
        if idx == -1:
            continue
        rest = sql[idx + len(kw) + 1 :].lstrip()
        first = rest.split(None, 1)[0].rstrip(",;)")
        first = first.strip('"').strip("`")
        if "." in first:
            return first
        if first:
            return f"ab6_learning_data.{first}"
    return None


def _extract_where(sql: str, params: dict) -> dict:
    upper = sql.upper()
    idx = upper.find(" WHERE ")
    if idx == -1:
        return {}
    tail = sql[idx + len(" WHERE ") :]
    for terminator in (" ORDER ", " GROUP ", " LIMIT ", " RETURNING ", " ON CONFLICT "):
        term_idx = upper.find(terminator, idx + len(" WHERE "))
        if term_idx != -1:
            tail = sql[idx + len(" WHERE ") : term_idx]
            break
    where: dict = {}
    parts = tail.split(" AND ")
    for part in parts:
        tokens = part.split("=")
        if len(tokens) != 2:
            continue
        key = tokens[0].strip().lstrip("(").rstrip(")")
        if key in params:
            where[key] = params[key]
    return where


def _is_where_key(name: str) -> bool:
    return name in {"uid", "cid", "seg", "sid", "limit", "itypes"}


def _row_matches(row: dict, where: dict) -> bool:
    for k, v in where.items():
        if row.get(_map_key(k)) != v:
            return False
    return True


def _map_key(param_key: str) -> str:
    return {
        "uid": "user_id",
        "cid": "challenge_id",
        "seg": "profile_segment",
        "sid": "session_id",
    }.get(param_key, param_key)


def _extract_select_columns(sql: str) -> list[str] | None:
    upper = sql.upper()
    try:
        start = upper.index("SELECT ") + len("SELECT ")
    except ValueError:
        return None
    end = upper.find(" FROM ", start)
    if end == -1:
        return None
    cols_raw = sql[start:end].strip()
    if cols_raw == "*":
        return ["*"]
    return [c.strip().split(".")[-1].strip('"') for c in cols_raw.split(",")]


def _ordered_values(row: dict) -> list:
    return [
        row.get("id"),
        row.get("email"),
        row.get("user_id"),
        row.get("cycle_id"),
        row.get("event_id"),
        row.get("event_type"),
        row.get("challenge_id"),
        row.get("slot_number"),
        row.get("attempt_no"),
        row.get("part_no"),
        row.get("note_no"),
        row.get("challenge_status"),
        row.get("start_time"),
        row.get("end_time"),
        row.get("score"),
        row.get("is_correct"),
        row.get("answer"),
        row.get("code_path"),
        row.get("run_no"),
        row.get("action"),
        row.get("occurred_at"),
        row.get("received_at"),
    ]


def _coerce(value: Any) -> Any:
    if isinstance(value, dict) and "_iso" in value:
        return value["_iso"]
    return value


def _seed_users() -> list[dict]:
    return [
        {
            "id": str(uuid.uuid4()),
            "email": "demo-learner@ab6.local",
            "full_name": "Demo Learner",
            "organization": "AB6 Demo",
            "mobile_number": None,
            "email_verified": True,
            "is_admin": False,
            "created_at": _utcnow(),
            "last_login": _utcnow(),
        }
    ]


def reset_for_tests() -> None:
    """Wipe all in-memory state.  Used by the test suite."""
    for k in list(MemorySession._state):
        MemorySession._state[k] = []


def export_state() -> dict[str, list[dict]]:
    """Snapshot of every in-memory table.  For the Streamlit 'Raw' tab."""
    return {k: list(v) for k, v in MemorySession._state.items()}
