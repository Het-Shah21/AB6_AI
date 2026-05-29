import json
import logging
from typing import Any

import numpy as np

from src.agent.state import OODAState
from src.db.repositories.wisdom_repo import WisdomRepo
from src.llm.provider import get_llm_for_purpose

logger = logging.getLogger(__name__)

DECIDE_SYSTEM_PROMPT = """You are an AI intervention strategist for a robotics education platform.
Based on the learner's diagnosis and available intervention types, select the best intervention.

Available intervention types:
- concept_explanation: Generate theory/formula explanation for a struggling concept
- video_recommendation: Recommend a specific video to re-watch
- prerequisite_nudge: Suggest going back to a prerequisite topic
- challenge_hint: Provide a targeted hint for the current challenge
- challenge_swap: Replace the next challenge with an AI-generated one
- revision_prompt: Spaced repetition review of a past concept
- encouragement: Motivational nudge when engagement drops

Respond with a JSON object:
{
    "selected_type": "concept_explanation",
    "target_concept": "concept_id",
    "rationale": "Brief explanation of why this intervention",
    "priority": "low|medium|high"
}
"""


def _segment_learner(learner_profile: dict) -> dict[str, Any]:
    mastery_map = learner_profile.get("mastery_map", {})
    mastery_values = [
        d.get("mastery", 0.5)
        for d in mastery_map.values()
        if isinstance(d, dict)
    ]
    avg_mastery = sum(mastery_values) / max(len(mastery_values), 1)

    learning_style = learner_profile.get("learning_style", {})
    struggle_count = len(learner_profile.get("engagement_history", []))

    return {
        "mastery_range": [
            round(max(0, avg_mastery - 0.2), 2),
            round(min(1, avg_mastery + 0.2), 2),
        ],
        "learning_style": learning_style.get("prefers", "mixed"),
        "struggle_count_gte": struggle_count,
    }


async def decide_node(state: OODAState) -> dict[str, Any]:
    user_id = state.get("user_id", "")
    diagnosed_struggles = state.get("diagnosed_struggles", [])
    learner_profile = state.get("learner_profile", {})
    engagement_score = state.get("engagement_score", 0.5)
    logger.info("DECIDE node: user=%s struggles=%s", user_id, diagnosed_struggles)

    decision = {
        "selected_type": "encouragement",
        "target_concept": diagnosed_struggles[0] if diagnosed_struggles else "",
        "rationale": "Fallback intervention (demo mode)",
        "priority": "low",
    }
    try:
        llm = await get_llm_for_purpose("primary")
        result = await llm.ainvoke([
            {"role": "system", "content": DECIDE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({
                    "diagnosed_struggles": diagnosed_struggles,
                    "engagement_score": engagement_score,
                    "learner_profile": {
                        "mastery_map": learner_profile.get("mastery_map", {}),
                        "learning_style": learner_profile.get("learning_style", {}),
                    },
                }, indent=2),
            },
        ])
        raw = str(result.content)
        try:
            decision = json.loads(raw)
        except json.JSONDecodeError:
            pass
    except Exception as e:
        logger.warning("LLM unavailable in demo mode: %s", e)

    intervention_type = decision.get("selected_type", "encouragement")
    target_concept = decision.get("target_concept", diagnosed_struggles[0] if diagnosed_struggles else "")

    segment = _segment_learner(learner_profile)
    candidates = []
    try:
        wisdom_repo = WisdomRepo()
        candidate_types = [
            "concept_explanation",
            "video_recommendation",
            "prerequisite_nudge",
            "challenge_hint",
            "encouragement",
        ]
        for ct in candidate_types:
            wisdom = await wisdom_repo.get_or_create(
                concept_id=target_concept or "general",
                intervention_type=ct,
                profile_segment=segment,
            )
            sample = float(np.random.beta(wisdom.alpha, wisdom.beta_param))
            candidates.append({
                "type": ct,
                "concept_id": target_concept,
                "thompson_sample": sample,
                "total_trials": wisdom.total_trials,
                "success_rate": wisdom.success_rate,
                "wisdom_id": str(wisdom.id),
            })
    except Exception as e:
        logger.warning("WisdomStore unavailable in demo mode: %s", e)
        candidates = [
            {"type": "encouragement", "concept_id": target_concept, "thompson_sample": 0.8,
             "total_trials": 0, "success_rate": 0.5},
        ]

    candidates.sort(key=lambda c: c["thompson_sample"], reverse=True)
    best = candidates[0] if candidates else None
    exploration = (best["total_trials"] < 10) if best else False

    selected = {
        "type": intervention_type,
        "concept_id": target_concept,
        "rationale": decision.get("rationale", ""),
        "priority": decision.get("priority", "low"),
        "candidates": candidates[:3],
        "exploration": exploration,
    }

    return {
        "selected_intervention": selected,
        "intervention_candidates": candidates,
        "exploration_flag": exploration,
        "messages": [
            {
                "role": "assistant",
                "content": f"DECIDE: {intervention_type} for {target_concept} "
                f"(exploration={exploration})",
            }
        ],
    }


def decide_router(state: OODAState) -> str:
    if state.get("should_pause", False):
        return "pause"
    return "act"
