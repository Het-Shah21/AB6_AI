import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.db.models.ai_wisdom_store import AIWisdomStore


class WisdomRepo:
    def __init__(self, session: AsyncSession | None = None):
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return await get_session()

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
        entry = result.scalar_one_or_none()
        if entry is None:
            entry = AIWisdomStore(
                concept_id=concept_id,
                intervention_type=intervention_type,
                profile_segment=profile_segment,
            )
            sess.add(entry)
            await sess.commit()
            await sess.refresh(entry)
        return entry

    async def update_beta(
        self,
        wisdom_id: str,
        success: bool,
    ) -> None:
        sess = await self._get_session()
        entry = await sess.get(
            AIWisdomStore, uuid.UUID(wisdom_id)
        )
        if entry is None:
            return
        if success:
            entry.alpha += 1.0
        else:
            entry.beta_param += 1.0
        entry.total_trials += 1
        entry.success_rate = entry.alpha / (
            entry.alpha + entry.beta_param
        )
        await sess.commit()

    async def get_by_concept(
        self, concept_id: str
    ) -> list[AIWisdomStore]:
        sess = await self._get_session()
        result = await sess.execute(
            select(AIWisdomStore).where(
                AIWisdomStore.concept_id == concept_id
            )
        )
        return list(result.scalars().all())
