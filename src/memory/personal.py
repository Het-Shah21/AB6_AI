import uuid
from typing import Any

from src.db.repositories.learner_profile_repo import LearnerProfileRepo
from src.db.repositories.intervention_repo import InterventionRepo
from src.db.models.ai_learner_profile import AILearnerProfile


class PersonalMemoryService:
    def __init__(self):
        self._profile_repo = LearnerProfileRepo()
        self._intervention_repo = InterventionRepo()

    async def get_profile(
        self, user_id: str
    ) -> AILearnerProfile | None:
        return await self._profile_repo.get(user_id)

    async def update_mastery(
        self,
        user_id: str,
        concept_id: str,
        mastery: float,
    ) -> AILearnerProfile:
        return await self._profile_repo.upsert_mastery(
            user_id, concept_id, mastery
        )

    async def record_struggle(
        self,
        user_id: str,
        concept_id: str,
        error_pattern: dict[str, Any],
    ) -> None:
        profile = await self._profile_repo.get(user_id)
        if profile is None:
            return
        patterns = dict(profile.struggle_patterns)
        if concept_id not in patterns:
            patterns[concept_id] = {
                "attempts": 0,
                "avg_score": 0.0,
                "common_errors": [],
            }
        entry = patterns[concept_id]
        entry["attempts"] = entry.get("attempts", 0) + 1
        entry["avg_score"] = (
            entry.get("avg_score", 0) * (entry["attempts"] - 1)
            + error_pattern.get("score", 0)
        ) / entry["attempts"]
        errors = list(entry.get("common_errors", []))
        new_error = error_pattern.get("error_type", "")
        if new_error and new_error not in errors:
            errors.append(new_error)
        entry["common_errors"] = errors[-10:]
        await self._profile_repo.update_struggle_patterns(
            user_id, {concept_id: entry}
        )

    async def get_intervention_history(
        self, user_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        logs = await self._intervention_repo.get_recent(
            user_id, limit
        )
        return [
            {
                "id": str(log.id),
                "type": log.intervention_type,
                "concepts": log.diagnosed_concepts,
                "effectiveness": log.effectiveness_label,
                "created_at": log.created_at.isoformat() if log.created_at else "",
            }
            for log in logs
        ]

    async def update_engagement(
        self,
        user_id: str,
        score: float,
        context: str = "",
    ) -> None:
        profile = await self._profile_repo.get(user_id)
        if profile is None:
            return
        history = list(profile.engagement_history)
        history.append({
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            "score": score,
            "context": context,
        })
        if len(history) > 100:
            history = history[-100:]
        profile.engagement_history = history
        session = await self._profile_repo._get_session()
        await session.commit()
