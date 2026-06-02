"""Guardrails, action whitelist, and HITL rules for the mentor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

InterventionType = Literal[
    "concept_explanation",
    "video_recommendation",
    "prerequisite_nudge",
    "challenge_hint",
    "challenge_swap",
    "revision_prompt",
    "encouragement",
]

ALL_INTERVENTION_TYPES: tuple[str, ...] = (
    "concept_explanation",
    "video_recommendation",
    "prerequisite_nudge",
    "challenge_hint",
    "challenge_swap",
    "revision_prompt",
    "encouragement",
)

# Stages where the mentor MUST pause and request human approval
# (curriculum modification, code execution, anything that touches a
# production database or affects the user's grading). These never fire
# automatically.
HIGH_STAKES: frozenset[str] = frozenset({
    "challenge_swap",  # replaces a graded challenge
    "revision_prompt",  # schedules spaced-repetition affecting pace
})

# Stages that are safe to push without a human in the loop
LOW_STAKES: frozenset[str] = frozenset({
    "concept_explanation",
    "video_recommendation",
    "prerequisite_nudge",
    "challenge_hint",
    "encouragement",
})

# Concepts whose unlock might break the curriculum sequence
SENSITIVE_CONCEPT_PREFIXES: tuple[str, ...] = (
    "final_exam",
    "capstone",
    "graded_assessment",
)


@dataclass(frozen=True)
class PolicyDecision:
    requires_human_approval: bool
    reasons: tuple[str, ...]


def evaluate(
    intervention_type: str,
    target_concept: str,
    cycle_count: int,
    cooldown_active: bool,
    consecutive_negative_feedback: int = 0,
) -> PolicyDecision:
    """Pure function: returns whether the action needs HITL and why."""
    reasons: list[str] = []

    if intervention_type not in ALL_INTERVENTION_TYPES:
        return PolicyDecision(True, (f"unknown_intervention_type:{intervention_type}",))

    if intervention_type in HIGH_STAKES:
        reasons.append(f"high_stakes_type:{intervention_type}")

    if any(target_concept.startswith(p) for p in SENSITIVE_CONCEPT_PREFIXES):
        reasons.append(f"sensitive_concept:{target_concept}")

    if consecutive_negative_feedback >= 3:
        reasons.append(f"repeated_failure:{consecutive_negative_feedback}")

    if cooldown_active and cycle_count > 0:
        reasons.append("cooldown_active")

    return PolicyDecision(bool(reasons), tuple(reasons))


def clamp_priority(priority: str) -> str:
    if priority not in ("low", "medium", "high"):
        return "low"
    return priority
