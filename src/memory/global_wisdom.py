import logging
from typing import Any

from src.db.repositories.wisdom_repo import WisdomRepo

logger = logging.getLogger(__name__)


class GlobalWisdomService:
    def __init__(self):
        self._wisdom_repo = WisdomRepo()

    async def get_intervention_stats(
        self,
        concept_id: str,
        intervention_type: str,
        profile_segment: dict[str, Any],
    ) -> dict[str, Any]:
        wisdom = await self._wisdom_repo.get_or_create(
            concept_id=concept_id,
            intervention_type=intervention_type,
            profile_segment=profile_segment,
        )
        return {
            "alpha": wisdom.alpha,
            "beta": wisdom.beta_param,
            "total_trials": wisdom.total_trials,
            "success_rate": wisdom.success_rate,
            "insight": wisdom.insight_text or "",
        }

    async def record_outcome(
        self,
        concept_id: str,
        intervention_type: str,
        profile_segment: dict[str, Any],
        success: bool,
    ) -> None:
        wisdom = await self._wisdom_repo.get_or_create(
            concept_id=concept_id,
            intervention_type=intervention_type,
            profile_segment=profile_segment,
        )
        await self._wisdom_repo.update_beta(str(wisdom.id), success)
        logger.info(
            "Recorded %s outcome for %s/%s (total=%d, rate=%.2f)",
            "success" if success else "failure",
            concept_id,
            intervention_type,
            wisdom.total_trials + 1,
            (wisdom.alpha + (1 if success else 0))
            / (wisdom.alpha + wisdom.beta_param + 1),
        )

    async def get_best_intervention(
        self,
        concept_id: str,
        profile_segment: dict[str, Any],
    ) -> dict[str, Any] | None:
        all_wisdom = await self._wisdom_repo.get_by_concept(concept_id)
        if not all_wisdom:
            return None

        best = None
        best_rate = -1.0
        for w in all_wisdom:
            rate = w.success_rate
            if w.total_trials >= 3 and rate > best_rate:
                best_rate = rate
                best = {
                    "intervention_type": w.intervention_type,
                    "success_rate": w.success_rate,
                    "total_trials": w.total_trials,
                    "insight": w.insight_text or "",
                }
        return best
