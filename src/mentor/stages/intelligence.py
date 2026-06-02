"""Stage 6 — INTELLIGENCE.

Combine policy decision + Thompson-sampled global wisdom + LLM reasoning
into the final `InterventionDecision`. This is where the model is
actually called.
"""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np

from src.mentor.memory.curriculum import CurriculumService
from src.mentor.memory.global_wisdom import GlobalWisdomService
from src.mentor.observability import get_logger, log_event
from src.mentor.state import (
    InferredState,
    IntelligenceDecision,
    InterpretedState,
    InterventionDecision,
    MentorState,
    PriorSnapshot,
)
from src.mentor.prompts import build_intelligence_prompt

logger = get_logger(__name__)


async def run(state: MentorState) -> dict[str, Any]:
    user_id: str = state["user_id"]
    cycle_id: uuid.UUID = state["cycle_id"]
    log_event(logger, "stage.intelligence.start", user=user_id, cycle=str(cycle_id))

    prior: PriorSnapshot = PriorSnapshot.model_validate(state["prior"])
    inferred: InferredState = InferredState.model_validate(state["inferred"])
    interpreted: InterpretedState = InterpretedState.model_validate(
        state["interpreted"]
    )

    wisdom = GlobalWisdomService()
    rng = np.random.default_rng(seed=hash((user_id, str(cycle_id))) & 0xFFFFFFFF)
    samples = await wisdom.sample(
        concept_id=interpreted.target_concept or "_",
        profile_segment={"skill_bucket": inferred.skill_bucket},
        intervention_types=interpreted.candidate_actions,
        rng=rng,
    )

    top = samples[0] if samples else None
    chosen_action = top["type"] if top else interpreted.candidate_actions[0]

    prompt = build_intelligence_prompt(
        prior=prior,
        inferred=inferred,
        interpreted=interpreted,
        thompson_top=samples[:3],
    )

    rationale = (
        f"thompson-winner={chosen_action} "
        f"(α={top['alpha']:.1f}, β={top['beta']:.1f}, "
        f"trials={top['total_trials']}); "
        f"policy={interpreted.policy_decision.decision}"
    )
    confidence = min(
        1.0,
        0.4 * float(top["thompson_sample"]) + 0.6 * inferred.confidence,
    )

    intel = IntelligenceDecision(
        chosen_action=chosen_action,
        rationale=rationale,
        thompson_samples=samples,
        prompt=prompt,
        confidence=confidence,
    )

    needs_approval = interpreted.policy_decision.requires_human_approval
    intervention = InterventionDecision(
        cycle_id=cycle_id,
        user_id=prior.user_id,
        action=chosen_action,
        target_concept=interpreted.target_concept,
        target_challenge=interpreted.target_challenge,
        rationale=rationale,
        confidence=confidence,
        requires_approval=needs_approval,
        policy_decision=interpreted.policy_decision,
        prompt=prompt,
        intelligence=intel,
    )

    log_event(
        logger,
        "stage.intelligence.end",
        user=user_id,
        action=chosen_action,
        confidence=confidence,
        needs_approval=needs_approval,
    )
    return {
        "intervention": intervention.model_dump(mode="json"),
        "stage_history": [
            {
                "stage": "intelligence",
                "status": "ok",
                "chosen_action": chosen_action,
            }
        ],
    }
