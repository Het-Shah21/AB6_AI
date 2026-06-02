import json
import logging
from typing import Any

from legacy.agent.state import OODAState
from src.db.repositories.learner_profile_repo import LearnerProfileRepo
from src.db.repositories.concept_repo import ConceptRepo
from src.db.repositories.benchmark_repo import BenchmarkRepo
from src.llm.provider import get_llm_for_purpose
from src.llm.sanitizer import sanitize_learner_summary

logger = logging.getLogger(__name__)

ORIENT_SYSTEM_PROMPT = """You are an AI learning diagnostician for a robotics education platform.
Analyze the learner's anonymized profile and produce a concise diagnosis.

Focus on:
1. Which concepts the learner is struggling with (mastery < 0.5)
2. Prerequisite knowledge gaps
3. How the learner compares to population benchmarks
4. Engagement trends (is it dropping?)
5. Learning style signals

Keep your analysis to 3-5 sentences. Be specific and actionable.
"""


async def orient_node(state: OODAState) -> dict[str, Any]:
    user_id = state.get("user_id", "")
    logger.info("ORIENT node: user=%s", user_id)

    profile = None
    mastery_map = {}
    struggle_patterns = {}
    learning_style = {}
    engagement_history = []
    prior_baseline = {}

    try:
        profile_repo = LearnerProfileRepo()
        concept_repo = ConceptRepo()
        benchmark_repo = BenchmarkRepo()
        profile = await profile_repo.get(user_id)
        mastery_map = dict(profile.mastery_map) if profile else {}
        struggle_patterns = dict(profile.struggle_patterns) if profile else {}
        learning_style = dict(profile.learning_style) if profile else {}
        engagement_history = list(profile.engagement_history) if profile else []
        prior_baseline = dict(profile.prior_baseline) if profile else {}
    except Exception as e:
        logger.warning("Could not load profile from DB (demo mode): %s", e)

    diagnosed_struggles = [
        cid
        for cid, data in mastery_map.items()
        if isinstance(data, dict) and data.get("mastery", 1.0) < 0.5
    ]

    derived = state.get("_derived_signals", {})
    engagement_score = _compute_engagement_score(mastery_map, derived)
    engagement_trend = _compute_engagement_trend(engagement_history)

    benchmarks = {}
    try:
        benchmark_repo_local = BenchmarkRepo()
        for cid in diagnosed_struggles:
            bm = await benchmark_repo_local.get(cid)
            if bm:
                benchmarks[cid] = {
                    "avg_mastery": bm.avg_mastery,
                    "p25_mastery": bm.p25_mastery,
                    "p75_mastery": bm.p75_mastery,
                }
    except Exception:
        pass

    learner_summary = sanitize_learner_summary({
        "mastery_map": mastery_map,
        "diagnosed_struggles": diagnosed_struggles,
        "engagement_score": engagement_score,
        "engagement_trend": engagement_trend,
        "error_rate": derived.get("error_rate", 0),
        "attempt_count": derived.get("total_attempts", 0),
        "struggle_patterns": struggle_patterns,
        "benchmarks": benchmarks,
    })

    diagnosis = "Based on the learner profile, no specific diagnosis could be generated (demo mode)."
    try:
        llm = await get_llm_for_purpose("reasoning")
        result = await llm.ainvoke([
            {"role": "system", "content": ORIENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Learner profile:\n{json.dumps(learner_summary, indent=2)}",
            },
        ])
        diagnosis = str(result.content)
    except Exception as e:
        logger.warning("LLM unavailable in demo mode: %s", e)
    logger.info("ORIENT diagnosis: %s", diagnosis[:120])

    concept_state = {}
    for cid, data in mastery_map.items():
        if isinstance(data, dict):
            concept_state[cid] = data
        elif isinstance(data, (int, float)):
            concept_state[cid] = {"mastery": float(data)}

    return {
        "learner_profile": {
            "mastery_map": mastery_map,
            "learning_style": learning_style,
            "engagement_history": engagement_history,
            "prior_baseline": prior_baseline,
        },
        "concept_state": concept_state,
        "diagnosed_struggles": diagnosed_struggles,
        "engagement_score": engagement_score,
        "messages": [
            {"role": "assistant", "content": f"ORIENT diagnosis: {diagnosis}"}
        ],
    }


def _compute_engagement_score(
    mastery_map: dict, derived: dict
) -> float:
    avg_mastery = 0.5
    if mastery_map:
        values = [
            d.get("mastery", 0.5)
            for d in mastery_map.values()
            if isinstance(d, dict)
        ]
        if values:
            avg_mastery = sum(values) / len(values)
    error_rate = derived.get("error_rate", 0)
    return max(0.0, min(1.0, avg_mastery * (1 - error_rate)))


def _compute_engagement_trend(
    history: list[dict[str, Any]],
) -> str:
    if len(history) < 2:
        return "stable"
    recent = [h.get("score", 0.5) for h in history[-5:]]
    if len(recent) < 2:
        return "stable"
    trend = recent[-1] - recent[0]
    if trend > 0.1:
        return "improving"
    if trend < -0.1:
        return "declining"
    return "stable"
