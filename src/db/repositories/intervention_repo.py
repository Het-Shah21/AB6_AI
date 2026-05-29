import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.db.models.ai_intervention_log import AIInterventionLog


class InterventionRepo:
    def __init__(self, session: AsyncSession | None = None):
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return await get_session()

    async def create(
        self,
        user_id: str,
        session_id: str,
        cycle_number: int,
        diagnosed_concepts: list[str],
        intervention_type: str,
        intervention_data: dict[str, Any],
        engagement_score: float | None = None,
        was_exploration: bool = False,
        arm_id: str | None = None,
    ) -> AIInterventionLog:
        sess = await self._get_session()
        entry = AIInterventionLog(
            user_id=uuid.UUID(user_id),
            session_id=session_id,
            cycle_number=cycle_number,
            diagnosed_concepts=diagnosed_concepts,
            intervention_type=intervention_type,
            intervention_data=intervention_data,
            engagement_score=engagement_score,
            was_exploration=was_exploration,
            arm_id=arm_id,
        )
        sess.add(entry)
        await sess.commit()
        await sess.refresh(entry)
        return entry

    async def update_effectiveness(
        self,
        intervention_id: str,
        next_challenge_score: float | None,
        score_delta: float | None,
        effectiveness_label: str | None,
    ) -> None:
        sess = await self._get_session()
        entry = await sess.get(
            AIInterventionLog, uuid.UUID(intervention_id)
        )
        if entry is None:
            return
        entry.next_challenge_score = next_challenge_score
        entry.score_delta = score_delta
        entry.effectiveness_label = effectiveness_label
        await sess.commit()

    async def get_recent(
        self, user_id: str, limit: int = 20
    ) -> list[AIInterventionLog]:
        sess = await self._get_session()
        result = await sess.execute(
            select(AIInterventionLog)
            .where(AIInterventionLog.user_id == uuid.UUID(user_id))
            .order_by(AIInterventionLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
