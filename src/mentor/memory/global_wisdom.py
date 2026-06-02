"""Global wisdom — Thompson-sampling priors shared across all learners.

Pure raw SQL so it works on ``postgres``, ``sqlite`` and ``memory``
backends.  When the table is missing, every method returns an empty
result instead of raising.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import numpy as np
from sqlalchemy import text

from src.db.engine import get_session
from src.mentor.observability import get_logger, log_event

logger = get_logger(__name__)


def _profile_segment_to_key(segment: dict) -> str:
    return json.dumps(segment, sort_keys=True, default=str)


def _ensure_uuid(value: str) -> str:
    return str(uuid.UUID(str(value)))


class GlobalWisdomService:
    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    async def _get_session(self):
        if self._session is not None:
            return self._session
        return await get_session()

    async def get_or_create(
        self,
        concept_id: str,
        intervention_type: str,
        profile_segment: dict,
    ) -> dict:
        sess = await self._get_session()
        seg = _profile_segment_to_key(profile_segment)
        result = await sess.execute(
            text(
                """
                SELECT id, alpha, beta_param, total_trials, success_rate
                FROM ab6_learning_data.ai_wisdom_store
                WHERE concept_id = :cid
                  AND intervention_type = :itype
                  AND profile_segment = :seg
                """
            ),
            {"cid": concept_id, "itype": intervention_type, "seg": seg},
        )
        row = result.one_or_none()
        if row is not None:
            return {
                "id": row[0],
                "alpha": float(row[1] or 1.0),
                "beta": float(row[2] or 1.0),
                "total_trials": int(row[3] or 0),
                "success_rate": float(row[4] or 0.5),
            }
        new_id = str(uuid.uuid4())
        await sess.execute(
            text(
                """
                INSERT INTO ab6_learning_data.ai_wisdom_store
                    (id, concept_id, intervention_type, profile_segment,
                     alpha, beta_param, total_trials, success_rate)
                VALUES (:id, :cid, :itype, :seg, 1.0, 1.0, 0, 0.5)
                """
            ),
            {
                "id": new_id,
                "cid": concept_id,
                "itype": intervention_type,
                "seg": seg,
            },
        )
        return {
            "id": new_id,
            "alpha": 1.0,
            "beta": 1.0,
            "total_trials": 0,
            "success_rate": 0.5,
        }

    async def fetch_for(
        self,
        concept_id: str,
        profile_segment: dict,
        intervention_types: list[str] | None = None,
    ) -> dict[str, dict]:
        try:
            sess = await self._get_session()
            seg = _profile_segment_to_key(profile_segment)
            params: dict[str, Any] = {"cid": concept_id, "seg": seg}
            sql = (
                "SELECT id, intervention_type, alpha, beta_param, total_trials, success_rate "
                "FROM ab6_learning_data.ai_wisdom_store "
                "WHERE concept_id = :cid AND profile_segment = :seg"
            )
            if intervention_types:
                sql += " AND intervention_type = ANY(:itypes)"
                params["itypes"] = list(intervention_types)
            result = await sess.execute(text(sql), params)
            out: dict[str, dict] = {}
            for r in result:
                out[r[1]] = {
                    "id": r[0],
                    "alpha": float(r[2] or 1.0),
                    "beta": float(r[3] or 1.0),
                    "total_trials": int(r[4] or 0),
                    "success_rate": float(r[5] or 0.5),
                }
            return out
        except Exception as exc:
            logger.warning("wisdom.fetch_for failed: %s", exc)
            return {}

    async def sample(
        self,
        concept_id: str,
        profile_segment: dict,
        intervention_types: list[str],
        rng: np.random.Generator,
    ) -> list[dict]:
        rows = await self.fetch_for(concept_id, profile_segment, intervention_types)
        candidates: list[dict] = []
        for itype in intervention_types:
            row = rows.get(itype)
            if row is None:
                row = await self.get_or_create(concept_id, itype, profile_segment)
            sample = float(rng.beta(row["alpha"], row["beta"]))
            candidates.append(
                {
                    "type": itype,
                    "thompson_sample": sample,
                    "alpha": row["alpha"],
                    "beta": row["beta"],
                    "total_trials": row["total_trials"],
                    "success_rate": row["success_rate"],
                    "wisdom_id": str(row["id"]),
                }
            )
        candidates.sort(key=lambda c: c["thompson_sample"], reverse=True)
        return candidates

    async def record_outcome(
        self,
        concept_id: str,
        intervention_type: str,
        profile_segment: dict,
        success: bool,
    ) -> dict:
        try:
            row = await self.get_or_create(concept_id, intervention_type, profile_segment)
            alpha = row["alpha"] + (1.0 if success else 0.0)
            beta = row["beta"] + (0.0 if success else 1.0)
            trials = row["total_trials"] + 1
            success_rate = alpha / (alpha + beta) if (alpha + beta) > 0 else 0.5
            sess = await self._get_session()
            await sess.execute(
                text(
                    """
                    UPDATE ab6_learning_data.ai_wisdom_store
                    SET alpha = :a, beta_param = :b,
                        total_trials = :t, success_rate = :sr
                    WHERE id = :id
                    """
                ),
                {
                    "a": alpha,
                    "b": beta,
                    "t": trials,
                    "sr": success_rate,
                    "id": str(row["id"]),
                },
            )
            log_event(
                logger,
                "wisdom.outcome.recorded",
                concept=concept_id,
                type=intervention_type,
                success=success,
                alpha=alpha,
                beta=beta,
            )
            return {
                "wisdom_id": str(row["id"]),
                "alpha": alpha,
                "beta": beta,
                "total_trials": trials,
                "success_rate": success_rate,
            }
        except Exception as exc:
            logger.warning("wisdom.record_outcome failed: %s", exc)
            return {}

    async def best_for(
        self,
        concept_id: str,
        profile_segment: dict,
        min_trials: int = 3,
    ) -> dict | None:
        rows = await self.fetch_for(concept_id, profile_segment)
        best: dict | None = None
        for itype, row in rows.items():
            if row["total_trials"] >= min_trials:
                if best is None or row["success_rate"] > best["success_rate"]:
                    best = {
                        "intervention_type": itype,
                        "success_rate": row["success_rate"],
                        "total_trials": row["total_trials"],
                        "alpha": row["alpha"],
                        "beta": row["beta"],
                    }
        return best
