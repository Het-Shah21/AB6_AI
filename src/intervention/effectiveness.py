import logging
from typing import Any

from src.db.repositories.intervention_repo import InterventionRepo
from src.db.repositories.learner_profile_repo import LearnerProfileRepo
from src.memory.global_wisdom import GlobalWisdomService

logger = logging.getLogger(__name__)


async def measure_effectiveness(
    intervention_id: str,
    user_id: str,
    concept_id: str,
    intervention_type: str,
    score_before: float,
    score_after: float,
    profile_segment: dict[str, Any] | None = None,
) -> str:
    score_delta = score_after - score_before
    if score_delta > 0.1:
        label = "positive"
        success = True
    elif score_delta < -0.1:
        label = "negative"
        success = False
    else:
        label = "neutral"
        success = bool(score_delta > 0)

    intervention_repo = InterventionRepo()
    await intervention_repo.update_effectiveness(
        intervention_id=intervention_id,
        next_challenge_score=score_after,
        score_delta=score_delta,
        effectiveness_label=label,
    )

    profile_repo = LearnerProfileRepo()
    await profile_repo.update_struggle_patterns(
        user_id,
        {
            f"effectiveness_{intervention_id}": {
                "label": label,
                "delta": score_delta,
                "concept": concept_id,
                "type": intervention_type,
            }
        },
    )

    gw = GlobalWisdomService()
    seg = profile_segment or {"mastery_range": [0, 1], "learning_style": "mixed", "struggle_count_gte": 0}
    await gw.record_outcome(
        concept_id=concept_id,
        intervention_type=intervention_type,
        profile_segment=seg,
        success=success,
    )

    logger.info(
        "Effectiveness: intervention=%s delta=%.2f label=%s",
        intervention_id,
        score_delta,
        label,
    )
    return label


def calibrate_difficulty(
    challenge: dict[str, Any],
    concept: dict[str, Any] | None,
) -> float:
    base = challenge.get("difficulty", 0.5)
    if concept:
        concept_diff = concept.get("difficulty", 0.5)
        base = (base + concept_diff) / 2.0
    return round(max(0.0, min(1.0, base)), 2)
