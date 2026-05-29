from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.db.models.ai_population_benchmark import AIPopulationBenchmark


class BenchmarkRepo:
    def __init__(self, session: AsyncSession | None = None):
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return await get_session()

    async def get(
        self, concept_id: str
    ) -> AIPopulationBenchmark | None:
        sess = await self._get_session()
        result = await sess.execute(
            select(AIPopulationBenchmark).where(
                AIPopulationBenchmark.concept_id == concept_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        concept_id: str,
        avg_mastery: float | None = None,
        median_mastery: float | None = None,
        p25_mastery: float | None = None,
        p75_mastery: float | None = None,
        avg_attempts: float | None = None,
        avg_time_to_master: float | None = None,
        common_prerequisite_gaps: list[str] | None = None,
        sample_size: int = 0,
    ) -> AIPopulationBenchmark:
        sess = await self._get_session()
        existing = await self.get(concept_id)
        if existing is None:
            entry = AIPopulationBenchmark(
                concept_id=concept_id,
                avg_mastery=avg_mastery,
                median_mastery=median_mastery,
                p25_mastery=p25_mastery,
                p75_mastery=p75_mastery,
                avg_attempts=avg_attempts,
                avg_time_to_master=avg_time_to_master,
                common_prerequisite_gaps=common_prerequisite_gaps,
                sample_size=sample_size,
            )
            sess.add(entry)
            await sess.commit()
            await sess.refresh(entry)
            return entry

        existing.avg_mastery = avg_mastery
        existing.median_mastery = median_mastery
        existing.p25_mastery = p25_mastery
        existing.p75_mastery = p75_mastery
        existing.avg_attempts = avg_attempts
        existing.avg_time_to_master = avg_time_to_master
        existing.common_prerequisite_gaps = common_prerequisite_gaps
        existing.sample_size = sample_size
        await sess.commit()
        await sess.refresh(existing)
        return existing
