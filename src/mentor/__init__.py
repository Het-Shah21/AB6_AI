"""Unified AB6 Mentor — 8-stage adaptive robotics mentor.

This package replaces the standalone OODA agent and YouTube agent with a
single dynamic pipeline that:

  1. PRIOR INFO   - loads user profile, struggle patterns, population
                    benchmarks, prior wisdom rows, curriculum progress
                    and recent challenge attempts.
  2. OBSERVE      - ingests the full JSON-line observation schema
                    (event_type, page, slot, attempt, part, note, code
                    path, metadata) and aggregates per-window signals.
  3. ANALYZE      - derives patterns, computes mastery deltas and
                    writes them back to ai_learner_profiles /
                    challenge_attempts / user_progress.
  4. INFERENCE    - consults PersonalMemoryService and
                    GlobalWisdomService, calls the LLM with both
                    contexts, deduces confusion vs clarity.
  5. INTERPRET    - cross-verifies inference against actual
                    challenge_attempts.score, user_progress.best_score
                    and population benchmarks; rejects unconfirmed
                    weaknesses.
  6. INTELLIGENCE - Thompson sampling across the 7 intervention types
                    with the LLM as a prior, applies the action
                    whitelist, decides HITL requirement.
  7. INTERVENTION - actually pushes the chosen intervention to the
                    user's WebSocket / SSE channel; persists
                    ai_intervention_log.
  8. FEEDBACK     - on the next cycle, compares score_before vs
                    score_after, updates ai_wisdom_store.alpha/beta
                    and user_progress, schedules the next review.
"""

from src.mentor.state import (
    MentorState,
    MentorEvent,
    PriorSnapshot,
    ObservedSignals,
    AnalyzedPattern,
    InferredState,
    InterpretedState,
    InterventionDecision,
    DeliveredIntervention,
    FeedbackRecord,
    create_initial_state,
)

__all__ = [
    "MentorState",
    "MentorEvent",
    "PriorSnapshot",
    "ObservedSignals",
    "AnalyzedPattern",
    "InferredState",
    "InterpretedState",
    "InterventionDecision",
    "DeliveredIntervention",
    "FeedbackRecord",
    "create_initial_state",
]
