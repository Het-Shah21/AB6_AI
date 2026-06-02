"""Prompt templates for the mentor's intelligence stage."""

from __future__ import annotations

from typing import Any

from src.mentor.state import InferredState, InterpretedState, PriorSnapshot


def build_intelligence_prompt(
    prior: PriorSnapshot,
    inferred: InferredState,
    interpreted: InterpretedState,
    thompson_top: list[dict[str, Any]],
) -> str:
    bullets = "\n".join(
        f"- {item['type']}: sample={item['thompson_sample']:.3f} "
        f"(α={item['alpha']:.1f}, β={item['beta']:.1f}, trials={item['total_trials']})"
        for item in thompson_top
    )
    return (
        "You are the intelligence layer of a multi-dynamic AI robotics mentor.\n\n"
        f"Learner: {prior.user_email or prior.user_id}\n"
        f"Organization: {prior.organization or 'unknown'}\n"
        f"Skill bucket: {inferred.skill_bucket} (confidence={inferred.confidence:.2f})\n"
        f"Root cause: {inferred.inferred_concept or 'unknown'}\n"
        f"Unmastered challenges: {', '.join(inferred.unmastered_challenges) or 'none'}\n"
        f"Population percentile: {prior.peer_percentile}\n\n"
        f"Summary: {interpreted.plain_english_summary}\n\n"
        f"Policy: {interpreted.policy_decision.decision}\n"
        f"Requires approval: {interpreted.policy_decision.requires_human_approval}\n\n"
        f"Top Thompson-sampled interventions:\n{bullets}\n\n"
        "Produce the final intervention copy. Be specific, brief, and "
        "actionable. Use plain language. If a code snippet helps, include "
        "it. Reference prior concepts only if the learner is in `intermediate` "
        "or higher."
    )
