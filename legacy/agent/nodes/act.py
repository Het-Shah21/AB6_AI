import logging
import uuid
from datetime import datetime
from typing import Any

from legacy.agent.state import OODAState
from src.db.repositories.learner_profile_repo import LearnerProfileRepo
from src.db.repositories.intervention_repo import InterventionRepo

logger = logging.getLogger(__name__)

INTERVENTION_TEMPLATES: dict[str, str] = {
    "concept_explanation": (
        "Here's a quick explanation: {concept_name} involves "
        "understanding how {description}. Think of it as {analogy}."
    ),
    "video_recommendation": (
        "Consider re-watching the video on {concept_name}. "
        "The key section starts around {timestamp}."
    ),
    "prerequisite_nudge": (
        "Before tackling {concept_name}, it might help to review "
        "{prerequisite_name} first. This will give you a stronger foundation."
    ),
    "challenge_hint": (
        "💡 Hint: For this challenge, think about how {hint_concept} applies. "
        "Try breaking the problem into smaller steps."
    ),
    "encouragement": (
        "You're making great progress! Keep going — "
        "you've already completed {completed_count} challenges."
    ),
    "revision_prompt": (
        "Quick revision: Can you recall the key formula for {concept_name}? "
        "It builds on what you learned earlier."
    ),
}


async def act_node(state: OODAState) -> dict[str, Any]:
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")
    selected = state.get("selected_intervention")
    cycle_count = state.get("cycle_count", 0)
    engagement_score = state.get("engagement_score", 0.5)
    diagnosed = state.get("diagnosed_struggles", [])

    logger.info(
        "ACT node: user=%s intervention=%s",
        user_id,
        selected.get("type") if selected else None,
    )

    if selected is None:
        return {
            "intervention_delivered": None,
            "delivery_channel": "none",
            "messages": [
                {"role": "assistant", "content": "ACT: no intervention selected"}
            ],
        }

    intervention_type = selected.get("type", "encouragement")
    concept_id = selected.get("concept_id", "")
    is_exploration = state.get("exploration_flag", False)

    intervention_id = str(uuid.uuid4())
    intervention_content = _build_intervention_content(
        intervention_type, concept_id, selected
    )

    intervention = {
        "intervention_id": intervention_id,
        "type": intervention_type,
        "content": intervention_content,
        "display": {
            "position": "bottom-right" if intervention_type == "encouragement" else "inline",
            "auto_dismiss_seconds": 10 if intervention_type == "encouragement" else None,
            "priority": selected.get("priority", "low"),
        },
        "metadata": {
            "concept_id": concept_id,
            "cycle_number": cycle_count,
        },
        "delivered_at": datetime.utcnow().isoformat(),
    }

    try:
        intervention_repo = InterventionRepo()
        await intervention_repo.create(
            user_id=user_id,
            session_id=session_id,
            cycle_number=cycle_count,
            diagnosed_concepts=diagnosed,
            intervention_type=intervention_type,
            intervention_data=intervention,
            engagement_score=engagement_score,
            was_exploration=is_exploration,
            arm_id=f"{concept_id}:{intervention_type}",
        )
        profile_repo = LearnerProfileRepo()
        await profile_repo.append_intervention(user_id, intervention)
    except Exception as e:
        logger.warning("Could not persist intervention (demo mode): %s", e)

    return {
        "intervention_delivered": intervention,
        "delivery_channel": "websocket",
        "cycle_count": cycle_count + 1,
        "last_cycle_timestamp": datetime.utcnow().isoformat(),
        "messages": [
            {
                "role": "assistant",
                "content": f"ACT: delivered {intervention_type} to user {user_id}",
            }
        ],
    }


def _build_intervention_content(
    intervention_type: str,
    concept_id: str,
    selected: dict[str, Any],
) -> dict[str, Any]:
    template = INTERVENTION_TEMPLATES.get(
        intervention_type,
        "Here's a helpful tip for your learning journey.",
    )
    body = template.format(
        concept_name=concept_id.replace("_", " ").replace(".", " -> "),
        description="the relationship between parameters and transformations",
        analogy="building blocks that stack on each other",
        timestamp="3:42",
        prerequisite_name="basic kinematics",
        hint_concept=concept_id.replace("_", " "),
        completed_count=5,
    )

    return {
        "title": selected.get("rationale", "")[:60] or f"Tip on {concept_id}",
        "body": body,
    }
