"""Stage 2 — OBSERVE.

Consume buffered events for this user, normalize them into a stream of
`MentorEvent` objects, and produce a `ObservedSignals` summary.

Sources:
  - Redis session buffer (peek, non-destructive)
  - Postgres observation_log (replay)
  - Live events already attached to the cycle
"""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from src.mentor.memory.observation_log import ObservationLogService
from src.mentor.memory.session import MentorSessionCache
from src.mentor.observability import get_logger, log_event
from src.mentor.state import MentorEvent, MentorState, ObservedSignals

logger = get_logger(__name__)


async def run(state: MentorState) -> dict[str, Any]:
    user_id: str = state["user_id"]
    cycle_id: uuid.UUID = state["cycle_id"]
    session_id: str = state.get("session_id", "default")
    log_event(logger, "stage.observe.start", user=user_id, cycle=str(cycle_id))

    cache = MentorSessionCache()
    obs_log = ObservationLogService()

    buffered = await cache.peek_events(user_id, count=100)
    replayed = await obs_log.fetch_for_session(user_id, session_id, limit=100)

    events: list[MentorEvent] = []

    for ev in buffered:
        try:
            events.append(MentorEvent.model_validate(ev))
        except Exception as exc:
            log_event(
                logger,
                "observe.event.invalid",
                error=str(exc),
                event_id=ev.get("event_id"),
            )

    for ev in replayed:
        try:
            ev.pop("id", None)
            ev.pop("cycle_id", None)
            ev.pop("occurred_at", None)
            events.append(MentorEvent.model_validate(ev))
        except Exception as exc:
            log_event(
                logger,
                "observe.replay.invalid",
                error=str(exc),
                event_id=ev.get("event_id"),
            )

    events.sort(key=lambda e: e.timestamp or 0)

    types = Counter(e.event_type for e in events)
    pages = Counter(e.page for e in events if e.page)
    challenges = Counter(e.challenge_id for e in events if e.challenge_id)
    focus_challenge = challenges.most_common(1)[0][0] if challenges else None
    focus_page = pages.most_common(1)[0][0] if pages else None

    signals = ObservedSignals(
        event_count=len(events),
        events=events,
        type_counts=dict(types),
        page_counts=dict(pages),
        challenge_counts=dict(challenges),
        focus_challenge_id=focus_challenge,
        focus_page=focus_page,
        session_id=session_id,
    )
    log_event(
        logger,
        "stage.observe.end",
        user=user_id,
        event_count=signals.event_count,
        focus_challenge=focus_challenge,
        focus_page=focus_page,
    )
    return {
        "observed": signals.model_dump(mode="json"),
        "stage_history": [{"stage": "observe", "status": "ok"}],
    }
