"""Global wisdom — Thompson-sampling priors shared across all learners."""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.db.models.ai_wisdom_store import AIWisdomStore
from src.mentor.observability import get_logger, log_event

logger = get_logger(__name__)


class GlobalWisdomService:
    """Beta-binomial wisdom keyed on (concept, intervention_type,
    profile_segment)."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return await get_session()

    @staticmethod
    def _profile_segment_to_key(segment: dict[str, Any]) -> str:
        """JSON-encodable deterministic key for the segment dict."""
        import json
        return json.dumps(segment, sort_keys=True, default=str)

    async def get_or_create(
        self,
        concept_id: str,
        intervention_type: str,
        profile_segment: dict[str, Any],
    ) -> AIWisdomStore:
        sess = await self._get_session()
        result = await sess.execute(
            select(AIWisdomStore).where(
                AIWisdomStore.concept_id == concept_id,
                AIWisdomStore.intervention_type == intervention_type,
                AIWisdomStore.profile_segment == profile_segment,
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row
        row = AIWisdomStore(
            concept_id=concept_id,
            intervention_type=intervention_type,
            profile_segment=profile_segment,
        )
        sess.add(row)
        await sess.commit()
        await sess.refresh(row)
        return row

    async def fetch_for(
        self,
        concept_id: str,
        profile_segment: dict[str, Any],
        intervention_types: list[str] | None = None,
    ) -> dict[str, AIWisdomStore]:
        """Return (intervention_type → wisdom) for sampling."""
        sess = await self._get_session()
        params: dict[str, Any] = {
            "cid": concept_id,
            "seg": self._profile_segment_to_key(profile_segment),
        }
        sql = (
            "SELECT id, concept_id, intervention_type, profile_segment, alpha, "
            "beta_param, total_trials, success_rate, insight_text "
            "FROM ab6_learning_data.ai_wisdom_store "
            "WHERE concept_id = :cid AND profile_segment = :seg::jsonb"
        )
        if intervention_types:
            sql += " AND intervention_type = ANY(:itypes)"
            params["itypes"] = list(intervention_types)
        result = await sess.execute(text(sql), params)
        out: dict[str, AIWisdomStore] = {}
        for r in result:
            row = AIWisdomStore(
                id=r[0],
                concept_id=r[1],
                intervention_type=r[2],
                profile_segment=r[3],
            )
            row.alpha = r[4]
            row.beta_param = r[5]
            row.total_trials = r[6]
            row.success_rate = r[7]
            row.insight_text = r[8]
            out[r[2]] = row
        return out

    async def sample(
        self,
        concept_id: str,
        profile_segment: dict[str, Any],
        intervention_types: list[str],
        rng: np.random.Generator,
    ) -> list[dict[str, Any]]:
        """Thompson sample for each candidate. Returns sorted desc by sample."""
        rows = await self.fetch_for(concept_id, profile_segment, intervention_types)
        candidates: list[dict[str, Any]] = []
        for itype in intervention_types:
            row = rows.get(itype)
            if row is None:
                row = await self.get_or_create(concept_id, itype, profile_segment)
            sample = float(rng.beta(row.alpha, row.beta_param))
            candidates.append(
                {
                    "type": itype,
                    "thompson_sample": sample,
                    "alpha": row.alpha,
                    "beta": row.beta_param,
                    "total_trials": row.total_trials,
                    "success_rate": row.success_rate,
                    "wisdom_id": str(row.id),
                }
            )
        candidates.sort(key=lambda c: c["thompson_sample"], reverse=True)
        return candidates

    async def record_outcome(
        self,
        concept_id: str,
        intervention_type: str,
        profile_segment: dict[str, Any],
        success: bool,
    ) -> dict[str, Any]:
        row = await self.get_or_create(
            concept_id, intervention_type, profile_segment
        )
        if success:
            row.alpha = float(row.alpha) + 1.0
        else:
            row.beta_param = float(row.beta_param) + 1.0
        row.total_trials = int(row.total_trials) + 1
        row.success_rate = float(row.alpha) / (row.alpha + row.beta_param)
        sess = await self._get_session()
        await sess.commit()
        log_event(
            logger,
            "wisdom.outcome.recorded",
            concept=concept_id,
            type=intervention_type,
            success=success,
            alpha=row.alpha,
            beta=row.beta_param,
        )
        return {
            "wisdom_id": str(row.id),
            "alpha": row.alpha,
            "beta": row.beta_param,
            "total_trials": row.total_trials,
            "success_rate": row.success_rate,
        }

    async def best_for(
        self,
        concept_id: str,
        profile_segment: dict[str, Any],
        min_trials: int = 3,
    ) -> dict[str, Any] | None:
        rows = await self.fetch_for(concept_id, profile_segment)
        best: dict[str, Any] | None = None
        for itype, row in rows.items():
            if int(row.total_trials) >= min_trials:
                if best is None or float(row.success_rate) > float(best["success_rate"]):
                    best = {
                        "intervention_type": itype,
                        "success_rate": float(row.success_rate),
                        "total_trials": int(row.total_trials),
                        "alpha": float(row.alpha),
                        "beta": float(row.beta_param),
                    }
        return best
