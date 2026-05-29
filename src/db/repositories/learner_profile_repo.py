import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.db.models.ai_learner_profile import AILearnerProfile


class LearnerProfileRepo:
    def __init__(self, session: AsyncSession | None = None):
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return await get_session()

    async def get(self, user_id: str) -> AILearnerProfile | None:
        session = await self._get_session()
        result = await session.execute(
            select(AILearnerProfile).where(
                AILearnerProfile.user_id == uuid.UUID(user_id)
            )
        )
        return result.scalar_one_or_none()

    async def upsert_mastery(
        self, user_id: str, concept_id: str, mastery: float
    ) -> AILearnerProfile:
        session = await self._get_session()
        profile = await self.get(user_id)
        if profile is None:
            profile = AILearnerProfile(
                user_id=uuid.UUID(user_id),
                mastery_map={concept_id: {"mastery": mastery}},
            )
            session.add(profile)
        else:
            mm = dict(profile.mastery_map)
            existing = mm.get(concept_id, {})
            if isinstance(existing, dict):
                existing["mastery"] = mastery
            mm[concept_id] = existing
            profile.mastery_map = mm
        await session.commit()
        await session.refresh(profile)
        return profile

    async def update_struggle_patterns(
        self, user_id: str, patterns: dict[str, Any]
    ) -> None:
        session = await self._get_session()
        profile = await self.get(user_id)
        if profile is None:
            return
        sp = dict(profile.struggle_patterns)
        sp.update(patterns)
        profile.struggle_patterns = sp
        await session.commit()

    async def append_intervention(
        self, user_id: str, intervention: dict[str, Any]
    ) -> None:
        session = await self._get_session()
        profile = await self.get(user_id)
        if profile is None:
            return
        ilog = list(profile.intervention_log)
        ilog.append(intervention)
        if len(ilog) > 100:
            ilog = ilog[-100:]
        profile.intervention_log = ilog
        await session.commit()
