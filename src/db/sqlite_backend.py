"""SQLite backend.

Used when ``MENTOR_BACKEND=sqlite``.  A single file holds the subset of
``ab6_learning_data`` and ``ab6_user_data`` the mentor needs.  Schema
names are flattened (``ab6_learning_data.ai_learner_profile`` becomes
``ai_learner_profile``) because SQLite has no multi-schema support.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from src.config.settings import get_settings
from src.mentor.observability import get_logger

logger = get_logger(__name__)


SCHEMA_DDL = [
    """CREATE TABLE IF NOT EXISTS user_details (
        id TEXT PRIMARY KEY,
        email TEXT,
        full_name TEXT,
        organization TEXT,
        mobile_number TEXT,
        email_verified INTEGER,
        is_admin INTEGER,
        created_at TEXT,
        last_login TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS challenges (
        id TEXT PRIMARY KEY,
        course_id TEXT,
        title TEXT,
        description TEXT,
        challenge_type TEXT,
        difficulty_level REAL,
        sequence INTEGER,
        locked INTEGER,
        require_special_lock INTEGER,
        special_unlock_challenge TEXT,
        special_unlock_score REAL,
        prerequisite_challenge_ids TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS user_progress (
        user_id TEXT, challenge_id TEXT,
        completed INTEGER, first_score REAL, best_score REAL,
        latest_score REAL, completed_at TEXT,
        PRIMARY KEY (user_id, challenge_id)
    )""",
    """CREATE TABLE IF NOT EXISTS challenge_attempts (
        id TEXT PRIMARY KEY, user_id TEXT, challenge_id TEXT,
        attempt_number INTEGER, score REAL, start_time TEXT,
        end_time TEXT, total_time REAL, submission_type TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS challenge_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id TEXT,
        run_number INTEGER, code_file TEXT, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS challenge_videos (
        id TEXT PRIMARY KEY, challenge_id TEXT, video_url TEXT, title TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_concept_mappings (
        concept_id TEXT, entity_id TEXT, entity_type TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_learner_profile (
        user_id TEXT PRIMARY KEY,
        mastery_map TEXT, learning_style TEXT, engagement_history TEXT,
        intervention_log TEXT, struggle_patterns TEXT, prior_baseline TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_intervention_log (
        id TEXT PRIMARY KEY, user_id TEXT, session_id TEXT,
        cycle_number INTEGER, diagnosed_concepts TEXT, engagement_score REAL,
        intervention_type TEXT, intervention_data TEXT, was_exploration INTEGER,
        arm_id TEXT, next_challenge_score REAL, score_delta REAL,
        effectiveness_label TEXT, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_population_benchmarks (
        user_id TEXT PRIMARY KEY, concept_id TEXT, percentile REAL,
        population_size INTEGER, avg_mastery REAL, median_mastery REAL
    )""",
    """CREATE TABLE IF NOT EXISTS ai_wisdom_store (
        id TEXT PRIMARY KEY, concept_id TEXT, intervention_type TEXT,
        profile_segment TEXT, alpha REAL, beta_param REAL,
        total_trials INTEGER, success_rate REAL, insight_text TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS mentor_observation_log (
        id TEXT PRIMARY KEY, event_id TEXT, user_id TEXT, session_id TEXT,
        cycle_id TEXT, received_at TEXT, occurred_at TEXT, event_type TEXT,
        page TEXT, page_id TEXT, challenge_id TEXT, slot_number INTEGER,
        attempt_no INTEGER, part_no INTEGER, note_no INTEGER,
        challenge_status TEXT, start_time TEXT, end_time TEXT, score REAL,
        is_correct INTEGER, answer TEXT, code_path TEXT, run_no INTEGER,
        action TEXT, metadata TEXT
    )""",
]


def _strip_schema(sql: str) -> str:
    """Map ab6_user_data.X -> X, ab6_learning_data.X -> X for SQLite."""
    return re.sub(
        r"ab6_(?:user_data|learning_data)\.([a-zA-Z_][a-zA-Z0-9_]*)",
        r"\1",
        sql,
    )


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteSession:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or get_settings().mentor_db_path
        self._conn: aiosqlite.Connection | None = None
        self._initialized = False

    async def _ensure(self) -> aiosqlite.Connection:
        if self._conn is not None:
            return self._conn
        os.makedirs(os.path.dirname(os.path.abspath(self._db_path)) or ".", exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        if not self._initialized:
            for ddl in SCHEMA_DDL:
                await self._conn.execute(ddl)
            await self._conn.commit()
            await self._seed_demo_user()
            self._initialized = True
        return self._conn

    async def _seed_demo_user(self) -> None:
        conn = await self._ensure()
        cur = await conn.execute("SELECT COUNT(*) FROM user_details")
        row = await cur.fetchone()
        if row and row[0] == 0:
            demo = (
                str(uuid.uuid4()),
                "demo-learner@ab6.local",
                "Demo Learner",
                "AB6 Demo",
                1,
                0,
                _utcnow(),
                _utcnow(),
            )
            await conn.execute(
                "INSERT INTO user_details "
                "(id, email, full_name, organization, "
                "email_verified, is_admin, created_at, last_login) "
                "VALUES (?,?,?,?,?,?,?,?)",
                demo,
            )
            await conn.commit()

    async def execute(self, statement: Any, params: dict | None = None) -> "SQLiteResult":
        sql = _strip_schema(str(statement).strip().rstrip(";"))
        flat_params = tuple(_flatten_params(sql, params or {}))
        conn = await self._ensure()
        cur = await conn.execute(sql, flat_params)
        if sql.upper().lstrip().startswith(("SELECT", "PRAGMA")):
            return SQLiteResult(await cur.fetchall(), cur.description)
        await conn.commit()
        return SQLiteResult([], cur.description)

    async def commit(self) -> None:
        if self._conn is not None:
            await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def refresh(self, instance: Any) -> None:
        return None


class SQLiteResult:
    def __init__(self, rows: list, description) -> None:
        self._rows = rows
        self._cols = [d[0] for d in (description or [])]

    def all(self) -> list[tuple]:
        return list(self._rows)

    def one_or_none(self) -> tuple | None:
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self) -> Any:
        return self._rows[0][0] if self._rows else None

    def scalars(self) -> "_SQLiteScalars":
        return _SQLiteScalars([r[0] if r else None for r in self._rows])


class _SQLiteScalars:
    def __init__(self, values: list) -> None:
        self._values = values

    def all(self) -> list:
        return list(self._values)


def _flatten_params(sql: str, params: dict) -> list:
    """Re-order params to match a naive ``?`` substitution based on the
    order keys appear in the SQL string.  Good enough for the queries
    the mentor actually runs.
    """
    keys = re.findall(r":([a-zA-Z_][a-zA-Z0-9_]*)", sql)
    seen: list = []
    for k in keys:
        if k in params and k not in seen:
            seen.append(k)
    extra = [k for k in params if k not in seen]
    return [params[k] for k in seen + extra]
