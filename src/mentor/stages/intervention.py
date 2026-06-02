"""Stage 7 — INTERVENTION.

Execute the chosen action. For high-stakes actions, this is where the
LangGraph `interrupt` happens; the cycle is parked until the human
approves. For low-stakes actions, we call the LLM and deliver the
content directly (WebSocket / SSE / DB record).
"""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.types import interrupt

from src.llm.provider import get_chat_model
from src.mentor.memory.curriculum import CurriculumService
from src.mentor.memory.observation_log import ObservationLogService
from src.mentor.memory.personal import PersonalMemoryService
from src.mentor.memory.session import MentorSessionCache
from src.mentor.observability import get_logger, log_event
from src.mentor.state import (
    DeliveredIntervention,
    InterventionDecision,
    MentorState,
)

logger = get_logger(__name__)


async def run(state: MentorState) -> dict[str, Any]:
    user_id: str = state["user_id"]
    cycle_id: uuid.UUID = state["cycle_id"]
    log_event(logger, "stage.intervention.start", user=user_id, cycle=str(cycle_id))

    intervention = InterventionDecision.model_validate(state["intervention"])

    if intervention.requires_approval:
        log_event(
            logger,
            "intervention.hitl.requested",
            action=intervention.action,
            rationale=intervention.rationale,
        )
        approval = interrupt(
            {
                "cycle_id": str(cycle_id),
                "user_id": str(user_id),
                "action": intervention.action,
                "rationale": intervention.rationale,
                "target_challenge": intervention.target_challenge,
                "target_concept": intervention.target_concept,
                "confidence": intervention.confidence,
                "prompt": intervention.prompt,
            }
        )
        if not approval or not approval.get("approved", False):
            log_event(
                logger,
                "intervention.hitl.rejected",
                cycle_id=str(cycle_id),
                action=intervention.action,
                reviewer=approval.get("reviewer") if approval else None,
            )
            return {
                "delivered": DeliveredIntervention(
                    cycle_id=cycle_id,
                    user_id=uuid.UUID(user_id) if not isinstance(user_id, uuid.UUID) else user_id,
                    action=intervention.action,
                    content="",
                    delivered=False,
                    blocked_by="human_approval",
                    feedback_id=None,
                ).model_dump(mode="json"),
                "stage_history": [
                    {
                        "stage": "intervention",
                        "status": "blocked_hitl",
                    }
                ],
            }
        intervention.approved_by = approval.get("reviewer")
        intervention.approval_notes = approval.get("notes")
        log_event(
            logger,
            "intervention.hitl.approved",
            cycle_id=str(cycle_id),
            action=intervention.action,
            reviewer=approval.get("reviewer"),
        )

    model = get_chat_model()
    response = await model.ainvoke(intervention.prompt)
    content = _extract_content(response)

    curriculum = CurriculumService()
    if intervention.action in {"challenge_swap", "video_recommendation"}:
        content = await _augment_with_resource(
            content, intervention, curriculum
        )

    cache = MentorSessionCache()
    await cache.set_cooldown(user_id, intervention.action, seconds=180)

    personal = PersonalMemoryService()
    await personal.append_intervention_to_profile(
        user_id=user_id,
        cycle_id=cycle_id,
        action=intervention.action,
        target_challenge=intervention.target_challenge,
        target_concept=intervention.target_concept,
        content=content,
    )

    log_event(
        logger,
        "intervention.delivered",
        action=intervention.action,
        user=user_id,
        cycle_id=str(cycle_id),
    )
    return {
        "delivered": DeliveredIntervention(
            cycle_id=cycle_id,
            user_id=uuid.UUID(user_id) if not isinstance(user_id, uuid.UUID) else user_id,
            action=intervention.action,
            content=content,
            delivered=True,
            blocked_by=None,
            feedback_id=None,
        ).model_dump(mode="json"),
        "stage_history": [
            {
                "stage": "intervention",
                "status": "delivered",
                "action": intervention.action,
            }
        ],
    }


def _extract_content(response: Any) -> str:
    if hasattr(response, "content"):
        c = response.content
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            out: list[str] = []
            for block in c:
                if isinstance(block, dict) and "text" in block:
                    out.append(str(block["text"]))
                else:
                    out.append(str(block))
            return "\n".join(out)
        return str(c)
    return str(response)


async def _augment_with_resource(
    content: str,
    intervention: InterventionDecision,
    curriculum: CurriculumService,
) -> str:
    concept = intervention.target_concept
    if not concept:
        return content
    if intervention.action == "video_recommendation":
        video = await curriculum.get_video_for_concept(concept)
        if video and video.get("video_url"):
            return f"{content}\n\nSuggested video: {video['video_url']} ({video['title']})"
    if intervention.action == "challenge_swap":
        challenges = await curriculum.get_challenges_for_concept(concept)
        unlocked = [c for c in challenges if not c.get("locked")]
        if unlocked:
            suggestion = unlocked[0]
            return f"{content}\n\nTry: {suggestion['title']} (id={suggestion['id']})"
    return content
