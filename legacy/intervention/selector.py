import logging
from typing import Any

import numpy as np

from src.db.repositories.wisdom_repo import WisdomRepo
from src.db.repositories.benchmark_repo import BenchmarkRepo
from legacy.concept_graph.queries import find_unmastered_prerequisites

logger = logging.getLogger(__name__)


async def select_intervention(
    concept_id: str,
    learner_profile: dict[str, Any],
    candidates: list[dict[str, Any]],
    wisdom_repo: WisdomRepo | None = None,
) -> dict[str, Any]:
    wr = wisdom_repo or WisdomRepo()
    best_sample = -1.0
    best_candidate = None

    mastery_map = learner_profile.get("mastery_map", {})
    engagement_history = learner_profile.get("engagement_history", [])
    avg_mastery = 0.5
    if mastery_map:
        vals = [
            d.get("mastery", 0.5)
            for d in mastery_map.values()
            if isinstance(d, dict)
        ]
        if vals:
            avg_mastery = sum(vals) / len(vals)

    learning_style = learner_profile.get("learning_style", {})
    segment = {
        "mastery_range": [
            round(max(0, avg_mastery - 0.2), 2),
            round(min(1, avg_mastery + 0.2), 2),
        ],
        "learning_style": learning_style.get("prefers", "mixed"),
        "struggle_count_gte": len(engagement_history),
    }

    for candidate in candidates:
        wisdom = await wr.get_or_create(
            concept_id=concept_id,
            intervention_type=candidate["type"],
            profile_segment=segment,
        )
        sample = float(np.random.beta(wisdom.alpha, wisdom.beta_param))
        if sample > best_sample:
            best_sample = sample
            best_candidate = {
                **candidate,
                "thompson_sample": sample,
                "exploration": wisdom.total_trials < 10,
                "wisdom_id": str(wisdom.id),
            }

    return best_candidate or candidates[0] if candidates else {}


def segment_learner(
    learner_profile: dict[str, Any],
) -> dict[str, Any]:
    mastery_map = learner_profile.get("mastery_map", {})
    vals = [
        d.get("mastery", 0.5)
        for d in mastery_map.values()
        if isinstance(d, dict)
    ]
    avg = sum(vals) / max(len(vals), 1) if vals else 0.5
    style = learner_profile.get("learning_style", {})
    return {
        "mastery_range": [round(max(0, avg - 0.2), 2), round(min(1, avg + 0.2), 2)],
        "learning_style": style.get("prefers", "mixed"),
        "struggle_count_gte": len(
            learner_profile.get("engagement_history", [])
        ),
    }


async def find_best_video_for_concept(
    concept_id: str,
) -> dict[str, Any] | None:
    from sqlalchemy import text
    from src.db.engine import get_session

    session = await get_session()
    result = await session.execute(
        text("""
            SELECT cv.id, cv.title, cv.url
            FROM ab6_learning_data.ai_concept_mappings acm
            JOIN ab6_data.challenge_videos cv ON cv.id = acm.entity_id
            WHERE acm.concept_id = :cid AND acm.entity_type = 'video'
            LIMIT 1
        """),
        {"cid": concept_id},
    )
    row = result.one_or_none()
    await session.close()
    if row:
        return {
            "video_id": str(row[0]),
            "title": row[1],
            "url": row[2],
            "concept_id": concept_id,
        }
    return None
