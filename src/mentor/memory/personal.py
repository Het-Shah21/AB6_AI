"""Personal memory — reads/writes AILearnerProfile and surrounding rows."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.db.models.ai_learner_profile import AILearnerProfile
from src.mentor.observability import get_logger, log_event

logger = get_logger(__name__)


class PersonalMemoryService:
    """All read/write paths against the learner's personal state."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return await get_session()

    # ── reads ────────────────────────────────────────────────────

    async def get_profile(self, user_id: str | uuid.UUID) -> AILearnerProfile | None:
        sess = await self._get_session()
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        result = await sess.execute(
            select(AILearnerProfile).where(AILearnerProfile.user_id == uid)
        )
        return result.scalar_one_or_none()

    async def get_or_create_profile(self, user_id: str | uuid.UUID) -> AILearnerProfile:
        profile = await self.get_profile(user_id)
        if profile is not None:
            return profile
        sess = await self._get_session()
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        profile = AILearnerProfile(
            user_id=uid,
            mastery_map={},
            learning_style={},
            engagement_history=[],
            intervention_log=[],
            struggle_patterns={},
            prior_baseline={},
        )
        sess.add(profile)
        await sess.commit()
        await sess.refresh(profile)
        return profile

    async def get_recent_intervention_history(
        self, user_id: str | uuid.UUID, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Read from ab6_learning_data.ai_intervention_log."""
        sess = await self._get_session()
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
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
            {"uid": str(uid), "limit": limit},
        )
        rows: list[dict[str, Any]] = []
        for r in result:
            rows.append(
                {
                    "id": str(r[0]),
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
                    "created_at": r[12].isoformat() if r[12] else None,
                }
            )
        return rows

    async def get_population_benchmarks(
        self, concept_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
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
        profile = await self.get_or_create_profile(user_id)
        key = concept_id or challenge or "_unknown"
        patterns = dict(profile.struggle_patterns or {})
        entry = dict(
            patterns.get(key) or {"attempts": 0, "avg_score": 0.0, "common_errors": []}
        )
        entry["attempts"] = int(entry.get("attempts", 0)) + 1
        if score is not None:
            n = entry["attempts"]
            entry["avg_score"] = (
                float(entry.get("avg_score", 0.0)) * (n - 1) + float(score)
            ) / n
        elif success is not None:
            entry["last_success"] = bool(success)
        errors = list(entry.get("common_errors") or [])
        if error_type and error_type not in errors:
            errors.append(error_type)
        entry["common_errors"] = errors[-10:]
        entry["last_challenge"] = challenge
        patterns[key] = entry
        profile.struggle_patterns = patterns
        sess = await self._get_session()
        await sess.commit()
        log_event(
            logger,
            "personal.struggle.recorded",
            concept=key,
            success=success,
        )

    async def upsert_mastery(
        self,
        user_id: str | uuid.UUID,
        concept_or_payload: str | dict[str, Any],
        mastery: float | None = None,
        attempts_delta: int = 0,
    ) -> None:
        profile = await self.get_or_create_profile(user_id)
        mm = dict(profile.mastery_map or {})

        if isinstance(concept_or_payload, dict):
            for cid, payload in concept_or_payload.items():
                existing = dict(mm.get(cid) or {})
                if "delta" in payload:
                    existing["mastery"] = max(
                        0.0, min(1.0, float(existing.get("mastery", 0.5)) + float(payload["delta"]))
                    )
                if "mastery" in payload:
                    existing["mastery"] = max(0.0, min(1.0, float(payload["mastery"])))
                existing["attempts"] = int(existing.get("attempts", 0)) + 1
                existing["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
                if "last_cycle" in payload:
                    existing["last_cycle"] = payload["last_cycle"]
                mm[cid] = existing
        else:
            cid = concept_or_payload
            existing = dict(mm.get(cid) or {})
            existing["mastery"] = max(0.0, min(1.0, float(mastery or 0.0)))
            existing["attempts"] = int(existing.get("attempts", 0)) + attempts_delta
            existing["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
            mm[cid] = existing

        profile.mastery_map = mm
        sess = await self._get_session()
        await sess.commit()
        log_event(logger, "personal.mastery.upsert", keys=list(mm.keys()))

    async def append_intervention_to_profile(
        self,
        user_id: str | uuid.UUID,
        cycle_id: str | uuid.UUID | None = None,
        action: str | None = None,
        target_challenge: str | None = None,
        target_concept: str | None = None,
        content: str | None = None,
        intervention: dict[str, Any] | None = None,
    ) -> None:
        if intervention is None:
            intervention = {
                "cycle_id": str(cycle_id) if cycle_id else None,
                "action": action,
                "target_challenge": target_challenge,
                "target_concept": target_concept,
                "content": content,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        profile = await self.get_or_create_profile(user_id)
        log = list(profile.intervention_log or [])
        log.append(intervention)
        if len(log) > 100:
            log = log[-100:]
        profile.intervention_log = log
        sess = await self._get_session()
        await sess.commit()
        log_event(logger, "personal.intervention.appended", action=action)

    async def update_engagement(
        self,
        user_id: str | uuid.UUID,
        score: float | None = None,
        context: str = "",
        success: bool | None = None,
        delta: float | None = None,
    ) -> None:
        profile = await self.get_or_create_profile(user_id)
        hist = list(profile.engagement_history or [])
        if score is None:
            if success is None and delta is None:
                score = 0.0
            else:
                score = float(delta or 0.0) + (0.1 if success else 0.0)
        hist.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "score": float(score),
                "context": context,
            }
        )
        if len(hist) > 100:
            hist = hist[-100:]
        profile.engagement_history = hist
        sess = await self._get_session()
        await sess.commit()

    async def population_benchmark(
        self, user_id: str | uuid.UUID
    ) -> dict[str, Any]:
        sess = await self._get_session()
        result = await sess.execute(
            text(
                """
                SELECT percentile, population_size
                FROM ab6_learning_data.ai_population_benchmarks
                WHERE user_id = :uid
                LIMIT 1
                """
            ),
            {"uid": str(user_id)},
        )
        row = result.one_or_none()
        if row is None:
            return {}
        return {
            "percentile": float(row[0]) if row[0] is not None else None,
            "population_size": int(row[1]) if row[1] is not None else 0,
        }

    async def serialize_profile(
        self, user_id: str | uuid.UUID
    ) -> dict[str, Any]:
        p = await self.get_or_create_profile(user_id)
        return {
            "mastery": p.mastery_map or {},
            "struggle_concepts": list((p.struggle_patterns or {}).keys()),
            "learning_style": p.learning_style or {},
            "engagement": (p.engagement_history or [])[-10:],
            "intervention_log": (p.intervention_log or [])[-10:],
            "prior_baseline": p.prior_baseline or {},
        }

    async def set_prior_baseline(
        self, user_id: str | uuid.UUID, baseline: dict[str, Any]
    ) -> None:
        profile = await self.get_or_create_profile(user_id)
        profile.prior_baseline = baseline
        sess = await self._get_session()
        await sess.commit()
