"""Stage 5 — INTERPRET.

Translate the inferred state into something the intelligence and
intervention stages can act on: a target concept, candidate actions,
constraints, and a plain-English summary for the LLM prompt.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.mentor.observability import get_logger, log_event
from src.mentor.policies import HIGH_STAKES, evaluate
from src.mentor.state import InferredState, InterpretedState, MentorState, PriorSnapshot

logger = get_logger(__name__)


ACTION_CATALOG = [
    "encouragement",
    "hint",
    "worked_example",
    "challenge_swap",
    "video_recommendation",
    "resource_link",
    "concept_recap",
    "revision_prompt",
    "session_break",
    "escalate_to_mentor",
]


async def run(state: MentorState) -> dict[str, Any]:
    user_id: str = state["user_id"]
    cycle_id: uuid.UUID = state["cycle_id"]
    log_event(logger, "stage.interpret.start", user=user_id, cycle=str(cycle_id))

    prior: PriorSnapshot = PriorSnapshot.model_validate(state["prior"])
    inferred: InferredState = InferredState.model_validate(state["inferred"])

    candidates: list[str] = []
    if inferred.skill_bucket == "stuck" and inferred.unmastered_challenges:
        candidates.extend(["worked_example", "video_recommendation", "challenge_swap"])
    if inferred.skill_bucket == "drifting":
        candidates.extend(["session_break", "encouragement"])
    if inferred.skill_bucket == "regressing":
        candidates.extend(["concept_recap", "resource_link"])
    if inferred.skill_bucket == "novice":
        candidates.extend(["hint", "worked_example", "concept_recap"])
    if inferred.skill_bucket == "intermediate":
        candidates.extend(["hint", "video_recommendation", "challenge_swap"])
    if inferred.skill_bucket == "advanced":
        candidates.extend(["challenge_swap", "revision_prompt"])
    if inferred.skill_bucket == "stuck" and len(candidates) == 0:
        candidates.append("escalate_to_mentor")

    if not candidates:
        candidates.append("encouragement")

    candidates = list(dict.fromkeys(candidates))

    decision = evaluate(
        candidate_actions=candidates,
        inferred=inferred,
        prior=prior,
    )

    summary = _summary(prior, inferred, candidates)

    interpreted = InterpretedState(
        target_concept=inferred.inferred_concept,
        target_challenge=(
            inferred.unmastered_challenges[0]
            if inferred.unmastered_challenges
            else None
        ),
        candidate_actions=candidates,
        policy_decision=decision,
        plain_english_summary=summary,
    )
    log_event(
        logger,
        "stage.interpret.end",
        user=user_id,
        target=interpreted.target_challenge,
        actions=candidates,
        requires_approval=decision.requires_human_approval,
    )
    return {
        "interpreted": interpreted.model_dump(mode="json"),
        "stage_history": [{"stage": "interpret", "status": "ok"}],
    }


def _summary(
    prior: PriorSnapshot,
    inferred: InferredState,
    candidates: list[str],
) -> str:
    return (
        f"Learner ({prior.user_email or prior.user_id}) is in bucket "
        f"`{inferred.skill_bucket}` with confidence {inferred.confidence:.2f}. "
        f"Root cause: {inferred.inferred_concept or 'unknown'}. "
        f"Candidate actions: {', '.join(candidates)}."
    )
