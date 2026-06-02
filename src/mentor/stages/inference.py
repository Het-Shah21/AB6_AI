"""Stage 4 — INFERENCE.

Combine the pattern with prior mastery to *infer* the learner's
hidden state: which concepts are unmastered, which concept is the
most likely root cause of the struggle, what skill bucket they
currently occupy, and how confident we are.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.mentor.observability import get_logger, log_event
from src.mentor.memory.curriculum import CurriculumService
from src.mentor.state import AnalyzedPattern, InferredState, MentorState, PriorSnapshot

logger = get_logger(__name__)


async def run(state: MentorState) -> dict[str, Any]:
    user_id: str = state["user_id"]
    cycle_id: uuid.UUID = state["cycle_id"]
    log_event(logger, "stage.inference.start", user=user_id, cycle=str(cycle_id))

    prior: PriorSnapshot = PriorSnapshot.model_validate(state["prior"])
    pattern: AnalyzedPattern = AnalyzedPattern.model_validate(state["analyzed"])

    curriculum = CurriculumService()
    struggle = pattern.struggle_challenges[0] if pattern.struggle_challenges else None
    inferred_concept: str | None = None
    concept_mastery: float | None = None
    if struggle:
        challenge = await curriculum.get_challenge(struggle)
        if challenge:
            inferred_concept = struggle
            concept_mastery = prior.mastery.get(struggle)

    completed = set(prior.completed_challenges)
    attempted = {
        a["challenge_id"] for a in prior.recent_attempts if a.get("challenge_id")
    }
    unmastered = sorted(
        (attempted | set(pattern.struggle_challenges)) - completed
    )

    skill_bucket = _classify_skill_bucket(prior, pattern)
    confidence = _compute_confidence(prior, pattern)

    inferred = InferredState(
        inferred_concept=inferred_concept,
        concept_mastery=concept_mastery,
        unmastered_challenges=unmastered,
        skill_bucket=skill_bucket,
        confidence=confidence,
        rationale=_build_rationale(prior, pattern, inferred_concept),
    )
    log_event(
        logger,
        "stage.inference.end",
        user=user_id,
        concept=inferred_concept,
        skill=skill_bucket,
        confidence=confidence,
    )
    return {
        "inferred": inferred.model_dump(mode="json"),
        "stage_history": [{"stage": "inference", "status": "ok"}],
    }


def _classify_skill_bucket(prior: PriorSnapshot, pattern: AnalyzedPattern) -> str:
    completed = len(prior.completed_challenges)
    if completed == 0 and len(prior.recent_attempts) <= 1:
        return "novice"
    if pattern.is_disengaged and pattern.failed_runs:
        return "stuck"
    if pattern.is_speed_drifting:
        return "drifting"
    if pattern.declining_challenges:
        return "regressing"
    if completed >= 10 and not pattern.struggle_challenges:
        return "advanced"
    if completed >= 4:
        return "intermediate"
    return "novice"


def _compute_confidence(prior: PriorSnapshot, pattern: AnalyzedPattern) -> float:
    evidence = 0
    if prior.mastery:
        evidence += 1
    if prior.completed_challenges:
        evidence += 1
    if prior.recent_attempts:
        evidence += 1
    if pattern.struggle_challenges or pattern.declining_challenges:
        evidence += 1
    if pattern.failed_runs:
        evidence += 1
    return min(1.0, 0.4 + 0.12 * evidence)


def _build_rationale(
    prior: PriorSnapshot,
    pattern: AnalyzedPattern,
    concept: str | None,
) -> str:
    bits: list[str] = []
    if pattern.struggle_challenges:
        bits.append(
            f"Failed runs on {', '.join(pattern.struggle_challenges[:2])}"
        )
    if pattern.declining_challenges:
        bits.append(
            f"Scores declining on {', '.join(pattern.declining_challenges[:2])}"
        )
    if pattern.hint_seeks:
        bits.append(f"{pattern.hint_seeks} hint requests")
    if pattern.is_disengaged:
        bits.append("inactivity > 5min")
    if concept:
        bits.append(f"root-cause = {concept}")
    return " | ".join(bits) or "no signal"
