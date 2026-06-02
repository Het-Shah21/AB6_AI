"""Personal memory — reads/writes learner state.

Uses raw SQL only so it works on all three backends
(``postgres``, ``sqlite``, ``memory``).  The ``mastery_map``,
``struggle_patterns`` and other JSON-typed columns are stored as TEXT
and JSON-encoded on write, JSON-decoded on read.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from src.db.engine import get_session
from src.mentor.observability import get_logger, log_event

logger = get_logger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_uuid(user_id: str | uuid.UUID) -> str:
    if isinstance(user_id, uuid.UUID):
        return str(user_id)
    return str(uuid.UUID(str(user_id)))


def _row_to_profile(row: tuple) -> dict:
    return {
        "user_id": row[0],
        "mastery_map": json.loads(row[1] or "{}"),
        "learning_style": json.loads(row[2] or "{}"),
        "engagement_history": json.loads(row[3] or "[]"),
        "intervention_log": json.loads(row[4] or "[]"),
        "struggle_patterns": json.loads(row[5] or "{}"),
        "prior_baseline": json.loads(row[6] or "{}"),
    }


class PersonalMemoryService:
    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    async def _get_session(self):
        if self._session is not None:
            return self._session
        return await get_session()

    # ── reads ────────────────────────────────────────────────────

    async def get_profile(self, user_id: str | uuid.UUID) -> dict | None:
        try:
            sess = await self._get_session()
            uid = _ensure_uuid(user_id)
            result = await sess.execute(
                text(
                    """
                    SELECT user_id, mastery_map, learning_style,
                           engagement_history, intervention_log,
                           struggle_patterns, prior_baseline
                    FROM ab6_learning_data.ai_learner_profile
                    WHERE user_id = :uid
                    """
                ),
                {"uid": uid},
            )
            row = result.one_or_none()
            if row is None:
                return None
            return _row_to_profile(row)
        except Exception as exc:
            logger.warning("personal.get_profile failed: %s", exc)
            return None

    async def get_or_create_profile(self, user_id: str | uuid.UUID) -> dict:
        existing = await self.get_profile(user_id)
        if existing is not None:
            return existing
        sess = await self._get_session()
        uid = _ensure_uuid(user_id)
        await sess.execute(
            text(
                """
                INSERT INTO ab6_learning_data.ai_learner_profile
                    (user_id, mastery_map, learning_style, engagement_history,
                     intervention_log, struggle_patterns, prior_baseline)
                VALUES (:uid, '{}', '{}', '[]', '[]', '{}', '{}')
                """
            ),
            {"uid": uid},
        )
        return await self.get_profile(user_id) or {
            "user_id": uid,
            "mastery_map": {},
            "learning_style": {},
            "engagement_history": [],
            "intervention_log": [],
            "struggle_patterns": {},
            "prior_baseline": {},
        }

    async def get_recent_intervention_history(
        self, user_id: str | uuid.UUID, limit: int = 20
    ) -> list[dict]:
        try:
            sess = await self._get_session()
            uid = _ensure_uuid(user_id)
            result = await sess.execute(
                text(
                    """
                    SELECT id, session_id, cycle_number, diagnosed_concepts,
                           engagement_score, intervention_type, intervention_data,
                           was_exploration, arm_id, next_challenge_score, score_delta,
                           effectiveness_label, created_at
                    FROM ab6_learning_data.ai_intervention_log
                    WHERE user_id = :uid
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"uid": uid, "limit": limit},
            )
            rows: list[dict] = []
            for r in result:
                rows.append(
                    {
                        "id": r[0],
                        "session_id": r[1],
                        "cycle_number": r[2],
                        "diagnosed_concepts": list(r[3] or []),
                        "engagement_score": r[4],
                        "intervention_type": r[5],
                        "intervention_data": r[6],
                        "was_exploration": r[7],
                        "arm_id": r[8],
                        "next_challenge_score": r[9],
                        "score_delta": r[10],
                        "effectiveness_label": r[11],
                        "created_at": r[12],
                    }
                )
            return rows
        except Exception as exc:
            logger.warning("personal.get_recent_intervention_history failed: %s", exc)
            return []

    async def get_population_benchmarks(
        self, concept_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        try:
            sess = await self._get_session()
            if not concept_ids:
                return {}
            result = await sess.execute(
                text(
                    """
                    SELECT concept_id, avg_mastery, median_mastery, p25_mastery,
                           p75_mastery, avg_attempts, avg_time_to_master, sample_size
                    FROM ab6_learning_data.ai_population_benchmarks
                    WHERE concept_id = ANY(:cids)
                    """
                ),
                {"cids": list(concept_ids)},
            )
            out: dict[str, dict[str, Any]] = {}
            for r in result:
                out[r[0]] = {
                    "avg_mastery": r[1],
                    "median_mastery": r[2],
                    "p25_mastery": r[3],
                    "p75_mastery": r[4],
                    "avg_attempts": r[5],
                    "avg_time_to_master": r[6],
                    "sample_size": r[7] or 0,
                }
            return out
        except Exception as exc:
            logger.warning("personal.get_population_benchmarks failed: %s", exc)
            return {}

    # ── writes ───────────────────────────────────────────────────

    async def record_struggle(
        self,
        user_id: str | uuid.UUID,
        concept_id: str | None = None,
        error_type: str | None = None,
        score: float | None = None,
        challenge: str | None = None,
        success: bool = False,
    ) -> None:
        try:
            profile = await self.get_or_create_profile(user_id)
            key = concept_id or challenge or "_unknown"
            patterns = dict(profile.get("struggle_patterns") or {})
            entry = dict(patterns.get(key) or {"attempts": 0, "avg_score": 0.0, "common_errors": []})
            entry["attempts"] = int(entry.get("attempts", 0)) + 1
            if score is not None:
                n = entry["attempts"]
                entry["avg_score"] = (
                    float(entry.get("avg_score", 0.0)) * (n - 1) + float(score)
                ) / n
            entry["last_success"] = bool(success)
            errors = list(entry.get("common_errors") or [])
            if error_type and error_type not in errors:
                errors.append(error_type)
            entry["common_errors"] = errors[-10:]
            entry["last_challenge"] = challenge
            patterns[key] = entry
            await self._write_field(user_id, "struggle_patterns", patterns)
            log_event(logger, "personal.struggle.recorded", concept=key)
        except Exception as exc:
            logger.warning("personal.record_struggle failed: %s", exc)

    async def upsert_mastery(
        self,
        user_id: str | uuid.UUID,
        concept_or_payload: str | dict[str, Any],
        mastery: float | None = None,
        attempts_delta: int = 0,
    ) -> None:
        try:
            profile = await self.get_or_create_profile(user_id)
            mm = dict(profile.get("mastery_map") or {})

            if isinstance(concept_or_payload, dict):
                for cid, payload in concept_or_payload.items():
                    existing = dict(mm.get(cid) or {})
                    if "delta" in payload:
                        existing["mastery"] = max(
                            0.0,
                            min(1.0, float(existing.get("mastery", 0.5)) + float(payload["delta"])),
                        )
                    if "mastery" in payload:
                        existing["mastery"] = max(0.0, min(1.0, float(payload["mastery"])))
                    existing["attempts"] = int(existing.get("attempts", 0)) + 1
                    existing["last_attempt_at"] = _utcnow_iso()
                    if "last_cycle" in payload:
                        existing["last_cycle"] = payload["last_cycle"]
                    mm[cid] = existing
            else:
                cid = concept_or_payload
                existing = dict(mm.get(cid) or {})
                existing["mastery"] = max(0.0, min(1.0, float(mastery or 0.0)))
                existing["attempts"] = int(existing.get("attempts", 0)) + attempts_delta
                existing["last_attempt_at"] = _utcnow_iso()
                mm[cid] = existing

            await self._write_field(user_id, "mastery_map", mm)
            log_event(logger, "personal.mastery.upsert", keys=list(mm.keys()))
        except Exception as exc:
            logger.warning("personal.upsert_mastery failed: %s", exc)

    async def append_intervention_to_profile(
        self,
        user_id: str | uuid.UUID,
        cycle_id: str | uuid.UUID | None = None,
        action: str | None = None,
        target_challenge: str | None = None,
        target_concept: str | None = None,
        content: str | None = None,
        intervention: dict | None = None,
    ) -> None:
        try:
            if intervention is None:
                intervention = {
                    "cycle_id": str(cycle_id) if cycle_id else None,
                    "action": action,
                    "target_challenge": target_challenge,
                    "target_concept": target_concept,
                    "content": content,
                    "ts": _utcnow_iso(),
                }
            profile = await self.get_or_create_profile(user_id)
            log = list(profile.get("intervention_log") or [])
            log.append(intervention)
            if len(log) > 100:
                log = log[-100:]
            await self._write_field(user_id, "intervention_log", log)
        except Exception as exc:
            logger.warning("personal.append_intervention_to_profile failed: %s", exc)

    async def update_engagement(
        self,
        user_id: str | uuid.UUID,
        score: float | None = None,
        context: str = "",
        success: bool | None = None,
        delta: float | None = None,
    ) -> None:
        try:
            profile = await self.get_or_create_profile(user_id)
            hist = list(profile.get("engagement_history") or [])
            if score is None:
                if success is None and delta is None:
                    score = 0.0
                else:
                    score = float(delta or 0.0) + (0.1 if success else 0.0)
            hist.append(
                {
                    "timestamp": _utcnow_iso(),
                    "score": float(score),
                    "context": context,
                }
            )
            if len(hist) > 100:
                hist = hist[-100:]
            await self._write_field(user_id, "engagement_history", hist)
        except Exception as exc:
            logger.warning("personal.update_engagement failed: %s", exc)

    async def set_prior_baseline(
        self, user_id: str | uuid.UUID, baseline: dict
    ) -> None:
        try:
            await self._write_field(user_id, "prior_baseline", baseline)
        except Exception as exc:
            logger.warning("personal.set_prior_baseline failed: %s", exc)

    async def population_benchmark(self, user_id: str | uuid.UUID) -> dict:
        try:
            sess = await self._get_session()
            uid = _ensure_uuid(user_id)
            result = await sess.execute(
                text(
                    """
                    SELECT percentile, population_size
                    FROM ab6_learning_data.ai_population_benchmarks
                    WHERE user_id = :uid
                    LIMIT 1
                    """
                ),
                {"uid": uid},
            )
            row = result.one_or_none()
            if row is None:
                return {}
            return {
                "percentile": float(row[0]) if row[0] is not None else None,
                "population_size": int(row[1]) if row[1] is not None else 0,
            }
        except Exception as exc:
            logger.warning("personal.population_benchmark failed: %s", exc)
            return {}

    async def serialize_profile(self, user_id: str | uuid.UUID) -> dict:
        profile = await self.get_profile(user_id)
        if profile is None:
            return {
                "mastery": {},
                "struggle_concepts": [],
                "learning_style": {},
                "engagement": [],
                "intervention_log": [],
                "prior_baseline": {},
            }
        return {
            "mastery": profile.get("mastery_map", {}),
            "struggle_concepts": list((profile.get("struggle_patterns") or {}).keys()),
            "learning_style": profile.get("learning_style", {}),
            "engagement": (profile.get("engagement_history") or [])[-10:],
            "intervention_log": (profile.get("intervention_log") or [])[-10:],
            "prior_baseline": profile.get("prior_baseline", {}),
        }

    # ── internals ────────────────────────────────────────────────

    _ALLOWED_FIELDS = {
        "mastery_map",
        "learning_style",
        "engagement_history",
        "intervention_log",
        "struggle_patterns",
        "prior_baseline",
    }

    async def _write_field(self, user_id: str | uuid.UUID, field: str, value: Any) -> None:
        if field not in self._ALLOWED_FIELDS:
            raise ValueError(f"refusing to write unknown field {field!r}")
        profile = await self.get_or_create_profile(user_id)
        profile[field] = value
        sess = await self._get_session()
        uid = _ensure_uuid(user_id)
        await sess.execute(
            text(
                f"""
                UPDATE ab6_learning_data.ai_learner_profile
                SET {field} = :val
                WHERE user_id = :uid
                """
            ),
            {"val": json.dumps(value, default=str), "uid": uid},
        )
