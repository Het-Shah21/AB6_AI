"""Reads from the AB6 backend curriculum tables.

Targets:
  ab6_user_data.user_details
  ab6_learning_data.events
  ab6_learning_data.courses
  ab6_learning_data.challenges
  ab6_learning_data.user_progress
  ab6_learning_data.challenge_attempts
  ab6_learning_data.challenge_runs
  ab6_learning_data.challenge_submissions
  ab6_learning_data.challenge_videos
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.mentor.observability import get_logger

logger = get_logger(__name__)


class CurriculumService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return await get_session()

    async def get_user(self, user_id: str | uuid.UUID) -> dict[str, Any] | None:
        try:
            sess = await self._get_session()
            uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
            result = await sess.execute(
                text(
                    """
                    SELECT id, email, full_name, organization, mobile_number,
                           email_verified, is_admin, created_at, last_login
                    FROM ab6_user_data.user_details
                    WHERE id = :uid
                    """
                ),
                {"uid": str(uid)},
            )
            row = result.one_or_none()
            if row is None:
                return None
            return {
                "id": str(row[0]),
                "email": row[1],
                "full_name": row[2],
                "organization": row[3],
                "mobile_number": row[4],
                "email_verified": row[5],
                "is_admin": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
                "last_login": row[8].isoformat() if row[8] else None,
            }
        except Exception as exc:
            logger.warning("curriculum.get_user failed: %s", exc)
            return None

    async def get_user_progress(
        self, user_id: str | uuid.UUID
    ) -> list[dict[str, Any]]:
        try:
            sess = await self._get_session()
            uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
            result = await sess.execute(
                text(
                    """
                    SELECT challenge_id, completed, first_score, best_score,
                           latest_score, completed_at
                    FROM ab6_learning_data.user_progress
                    WHERE user_id = :uid
                    ORDER BY completed_at DESC
                    """
                ),
                {"uid": str(uid)},
            )
            return [
                {
                    "challenge_id": r[0],
                    "completed": bool(r[1]),
                    "first_score": r[2],
                    "best_score": r[3],
                    "latest_score": r[4],
                    "completed_at": r[5] if r[5] else None,
                }
                for r in result
            ]
        except Exception as exc:
            logger.warning("curriculum.get_user_progress failed: %s", exc)
            return []

    async def get_recent_challenge_attempts(
        self,
        user_id: str | uuid.UUID,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        try:
            sess = await self._get_session()
            uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
            result = await sess.execute(
                text(
                    """
                    SELECT challenge_id, attempt_number, score, start_time, end_time,
                           total_time, submission_type
                    FROM ab6_learning_data.challenge_attempts
                    WHERE user_id = :uid
                    ORDER BY start_time DESC
                    LIMIT :limit
                    """
                ),
                {"uid": str(uid), "limit": limit},
            )
            return [
                {
                    "challenge_id": r[0],
                    "attempt_number": r[1],
                    "score": r[2],
                    "start_time": r[3] if r[3] else None,
                    "end_time": r[4] if r[4] else None,
                    "total_time": r[5],
                    "submission_type": r[6],
                }
                for r in result
            ]
        except Exception as exc:
            logger.warning("curriculum.get_recent_challenge_attempts failed: %s", exc)
            return []

    async def get_challenge_runs(
        self, user_id: str | uuid.UUID, limit: int = 50
    ) -> list[dict[str, Any]]:
        try:
            sess = await self._get_session()
            uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
            result = await sess.execute(
                text(
                    """
                    SELECT cr.attempt_id, cr.run_number, cr.code_file, cr.created_at,
                           ca.challenge_id, ca.attempt_number
                    FROM ab6_learning_data.challenge_runs cr
                    JOIN ab6_learning_data.challenge_attempts ca
                      ON ca.id = cr.attempt_id
                    WHERE ca.user_id = :uid
                    ORDER BY cr.created_at DESC
                    LIMIT :limit
                    """
                ),
                {"uid": str(uid), "limit": limit},
            )
            return [
                {
                    "attempt_id": str(r[0]),
                    "run_number": r[1],
                    "code_file": r[2],
                    "created_at": r[3] if r[3] else None,
                    "challenge_id": r[4],
                    "attempt_number": r[5],
                }
                for r in result
            ]
        except Exception as exc:
            logger.warning("curriculum.get_challenge_runs failed: %s", exc)
            return []

    async def get_challenge(
        self, challenge_id: str
    ) -> dict[str, Any] | None:
        try:
            sess = await self._get_session()
            result = await sess.execute(
                text(
                    """
                    SELECT id, course_id, title, description, challenge_type,
                           difficulty_level, sequence, locked, require_special_lock,
                           special_unlock_challenge, special_unlock_score,
                           prerequisite_challenge_ids
                    FROM ab6_learning_data.challenges
                    WHERE id = :cid
                    """
                ),
                {"cid": challenge_id},
            )
            row = result.one_or_none()
            if row is None:
                return None
            return {
                "id": row[0],
                "course_id": str(row[1]) if row[1] is not None else None,
                "title": row[2],
                "description": row[3],
                "challenge_type": row[4],
                "difficulty_level": row[5],
                "sequence": row[6],
                "locked": bool(row[7]),
                "require_special_lock": bool(row[8]) if row[8] is not None else False,
                "special_unlock_challenge": row[9],
                "special_unlock_score": row[10],
                "prerequisite_challenge_ids": list(row[11] or []),
            }
        except Exception as exc:
            logger.warning("curriculum.get_challenge failed: %s", exc)
            return None

    async def get_challenges_for_concept(
        self, concept_id: str
    ) -> list[dict[str, Any]]:
        try:
            sess = await self._get_session()
            result = await sess.execute(
                text(
                    """
                    SELECT c.id, c.title, c.challenge_type, c.difficulty_level,
                           c.sequence, c.locked, c.prerequisite_challenge_ids
                    FROM ab6_learning_data.challenges c
                    JOIN ab6_learning_data.ai_concept_mappings m
                      ON m.entity_id = c.id AND m.entity_type = 'challenge'
                    WHERE m.concept_id = :cid
                    ORDER BY c.sequence ASC
                    """
                ),
                {"cid": concept_id},
            )
            return [
                {
                    "id": r[0],
                    "title": r[1],
                    "challenge_type": r[2],
                    "difficulty_level": r[3],
                    "sequence": r[4],
                    "locked": bool(r[5]),
                    "prerequisite_challenge_ids": list(r[6] or []),
                }
                for r in result
            ]
        except Exception as exc:
            logger.warning("curriculum.get_challenges_for_concept failed: %s", exc)
            return []

    async def get_video_for_concept(
        self, concept_id: str
    ) -> dict[str, Any] | None:
        try:
            sess = await self._get_session()
            result = await sess.execute(
                text(
                    """
                    SELECT cv.id, cv.video_url, c.title
                    FROM ab6_learning_data.challenge_videos cv
                    JOIN ab6_learning_data.challenges c ON c.id = cv.challenge_id
                    JOIN ab6_learning_data.ai_concept_mappings m
                      ON m.entity_id = cv.challenge_id AND m.entity_type = 'video'
                    WHERE m.concept_id = :cid
                    ORDER BY cv.id
                    LIMIT 1
                    """
                ),
                {"cid": concept_id},
            )
            row = result.one_or_none()
            if row is None:
                return None
            return {
                "video_id": str(row[0]),
                "video_url": row[1],
                "title": row[2],
                "concept_id": concept_id,
            }
        except Exception as exc:
            logger.warning("curriculum.get_video_for_concept failed: %s", exc)
            return None

    async def update_user_progress_score(
        self,
        user_id: str | uuid.UUID,
        challenge_id: str,
        score: float,
        completed: bool = False,
    ) -> None:
        try:
            sess = await self._get_session()
            uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
            await sess.execute(
                text(
                    """
                    INSERT INTO ab6_learning_data.user_progress
                        (user_id, challenge_id, completed, first_score, best_score,
                         latest_score, completed_at)
                    VALUES (:uid, :cid, :completed, :score, :score, :score, :ts)
                    """
                ),
                {
                    "uid": str(uid),
                    "cid": challenge_id,
                    "score": score,
                    "completed": 1 if completed else 0,
                    "ts": datetime.now(timezone.utc).isoformat() if completed else None,
                },
            )
        except Exception as exc:
            logger.warning("curriculum.update_user_progress_score failed: %s", exc)

    async def get_unmastered_prerequisites(
        self,
        user_id: str | uuid.UUID,
        challenge_id: str,
    ) -> list[str]:
        challenge = await self.get_challenge(challenge_id)
        if not challenge:
            return []
        prereq_ids = list(challenge.get("prerequisite_challenge_ids") or [])
        if not prereq_ids:
            return []
        progress = await self.get_user_progress(user_id)
        completed_ids = {p["challenge_id"] for p in progress if p["completed"]}
        return [pid for pid in prereq_ids if pid not in completed_ids]
