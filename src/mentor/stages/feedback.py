"""Stage 8 — FEEDBACK LOOP.

After delivery, observe what happens next:
  - did the learner try again, get a higher score, watch the video?
  - update personal mastery
  - update global wisdom (Thompson α/β)
  - log the cycle to ai_cycle_log for the legacy store
"""

from __future__ import annotations

import uuid
from typing import Any

from src.mentor.memory.global_wisdom import GlobalWisdomService
from src.mentor.memory.observation_log import ObservationLogService
from src.mentor.memory.personal import PersonalMemoryService
from src.mentor.observability import get_logger, log_event
from src.mentor.state import (
    DeliveredIntervention,
    FeedbackRecord,
    InterventionDecision,
    MentorState,
    ObservedSignals,
)

logger = get_logger(__name__)


async def run(state: MentorState) -> dict[str, Any]:
    user_id: str = state["user_id"]
    cycle_id: uuid.UUID = state["cycle_id"]
    log_event(logger, "stage.feedback.start", user=user_id, cycle=str(cycle_id))

    observed: ObservedSignals | None = None
    if state.get("observed"):
        try:
            observed = ObservedSignals.model_validate(state["observed"])
        except Exception:
            observed = None

    delivered: DeliveredIntervention | None = None
    if state.get("delivered"):
        delivered = DeliveredIntervention.model_validate(state["delivered"])

    intervention: InterventionDecision | None = None
    if state.get("intervention"):
        intervention = InterventionDecision.model_validate(state["intervention"])

    success = _evaluate_success(observed, intervention)
    delta = _score_delta(observed, intervention)

    wisdom = GlobalWisdomService()
    segment = {"skill_bucket": state["inferred"].get("skill_bucket", "novice")}
    await wisdom.record_outcome(
        concept_id=intervention.target_concept if intervention else "_",
        intervention_type=intervention.action if intervention else "_",
        profile_segment=segment,
        success=success,
    )

    personal = PersonalMemoryService()
    if intervention and intervention.target_concept:
        mastery_delta = 0.05 if success else -0.02
        await personal.upsert_mastery(
            user_id,
            {
                intervention.target_concept: {
                    "delta": mastery_delta,
                    "last_cycle": str(cycle_id),
                }
            },
        )
    await personal.record_struggle(
        user_id,
        concept=intervention.target_concept if intervention else None,
        challenge=intervention.target_challenge if intervention else None,
        success=success,
    )
    await personal.update_engagement(user_id, success=success, delta=delta)

    feedback = FeedbackRecord(
        cycle_id=cycle_id,
        action=intervention.action if intervention else None,
        success=success,
        score_delta=delta,
        delivered=delivered.delivered if delivered else False,
    )
    log_event(
        logger,
        "stage.feedback.end",
        user=user_id,
        cycle_id=str(cycle_id),
        success=success,
        delta=delta,
    )
    return {
        "feedback": feedback.model_dump(mode="json"),
        "stage_history": [
            {
                "stage": "feedback",
                "status": "ok",
                "success": success,
                "delta": delta,
            }
        ],
    }


def _evaluate_success(
    observed: ObservedSignals | None, intervention: InterventionDecision | None
) -> bool:
    if observed is None or intervention is None:
        return False
    action = intervention.action
    focus = observed.focus_challenge_id
    after = [
        e
        for e in observed.events
        if e.challenge_id == focus
        and (e.event_type in {"code_run", "submission", "challenge_submit"})
        and (intervention.target_challenge is None or e.challenge_id == intervention.target_challenge)
    ]
    if not after:
        return False
    if action in {"session_break"}:
        return False  # break success is a longer-term outcome
    if action in {"challenge_swap", "video_recommendation"}:
        return any(e.event_type == "code_run" for e in after)
    if action in {"hint", "worked_example", "concept_recap", "resource_link"}:
        return any(e.is_correct is True for e in after) or any(
            (e.score or 0) > 0 for e in after
        )
    return True


def _score_delta(
    observed: ObservedSignals | None, intervention: InterventionDecision | None
) -> float:
    if observed is None or intervention is None:
        return 0.0
    scores = [
        float(e.score)
        for e in observed.events
        if e.score is not None
        and e.challenge_id == intervention.target_challenge
    ]
    if len(scores) < 2:
        return 0.0
    return scores[-1] - scores[0]
