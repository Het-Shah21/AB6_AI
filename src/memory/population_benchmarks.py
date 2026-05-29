import logging
from typing import Any

from sqlalchemy import text

from src.db.engine import get_session
from src.db.repositories.benchmark_repo import BenchmarkRepo

logger = logging.getLogger(__name__)


class PopulationBenchmarkService:
    def __init__(self):
        self._benchmark_repo = BenchmarkRepo()

    async def get_benchmark(
        self, concept_id: str
    ) -> dict[str, Any] | None:
        bm = await self._benchmark_repo.get(concept_id)
        if bm is None:
            return None
        return {
            "concept_id": bm.concept_id,
            "avg_mastery": bm.avg_mastery,
            "median_mastery": bm.median_mastery,
            "p25_mastery": bm.p25_mastery,
            "p75_mastery": bm.p75_mastery,
            "avg_attempts": bm.avg_attempts,
            "avg_time_to_master": bm.avg_time_to_master,
            "sample_size": bm.sample_size,
        }

    async def recalculate_all(self) -> dict[str, int]:
        session = await get_session()
        result = await session.execute(
            text("""
                SELECT
                    concept_id,
                    AVG(mastery) as avg_m,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mastery) as med_m,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY mastery) as p25_m,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY mastery) as p75_m,
                    AVG(attempts) as avg_att,
                    COUNT(*) as sample
                FROM (
                    SELECT
                        key as concept_id,
                        CAST(value->>'mastery' AS FLOAT) as mastery,
                        CAST(value->>'attempts' AS INTEGER) as attempts
                    FROM ab6_learning_data.ai_learner_profiles,
                    jsonb_each(mastery_map)
                ) sub
                GROUP BY concept_id
            """)
        )
        count = 0
        for row in result:
            await self._benchmark_repo.upsert(
                concept_id=row[0],
                avg_mastery=float(row[1]) if row[1] else None,
                median_mastery=float(row[2]) if row[2] else None,
                p25_mastery=float(row[3]) if row[3] else None,
                p75_mastery=float(row[4]) if row[4] else None,
                avg_attempts=float(row[5]) if row[5] else None,
                sample_size=int(row[6]) if row[6] else 0,
            )
            count += 1

        logger.info("Recalculated benchmarks for %d concepts", count)
        await session.close()
        return {"concepts_updated": count}
