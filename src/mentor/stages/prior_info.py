"""Stage 1 — PRIOR INFO.

Load everything the mentor already knows about the learner from
short-term (Redis), long-term (Postgres profile), and population
(global wisdom, peer benchmarks) stores. Emit a `PriorSnapshot`.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.mentor.memory.curriculum import CurriculumService
from src.mentor.memory.observation_log import ObservationLogService
from src.mentor.memory.personal import PersonalMemoryService
from src.mentor.memory.session import MentorSessionCache
from src.mentor.observability import get_logger, log_event
from src.mentor.state import MentorState, PriorSnapshot

logger = get_logger(__name__)


async def run(state: MentorState) -> dict[str, Any]:
    user_id: str = state["user_id"]
    cycle_id: uuid.UUID = state["cycle_id"]
    log_event(logger, "stage.prior_info.start", user=user_id, cycle=str(cycle_id))

    cache = MentorSessionCache()
    personal = PersonalMemoryService()
    curriculum = CurriculumService()
    obs_log = ObservationLogService()

    cached_state = await cache.get_state(user_id)
    cached_events = await cache.peek_events(user_id, count=50)

    profile = await personal.serialize_profile(user_id)
    cold_start = not profile.get("mastery") and not profile.get("intervention_log")
    if cold_start:
        await personal.upsert_mastery(user_id, {})

    user_row = await curriculum.get_user(user_id)
    progress = await curriculum.get_user_progress(user_id)
    recent_attempts = await curriculum.get_recent_challenge_attempts(user_id, limit=10)

    pop_bench = await personal.population_benchmark(user_id)

    snapshot = PriorSnapshot(
        user_id=uuid.UUID(user_id) if not isinstance(user_id, uuid.UUID) else user_id,
        user_email=user_row.get("email") if user_row else None,
        full_name=user_row.get("full_name") if user_row else None,
        organization=user_row.get("organization") if user_row else None,
        mastery=profile.get("mastery", {}),
        struggles=profile.get("struggle_concepts", []),
        last_intervention_at=(
            profile["intervention_log"][-1].get("ts")
            if profile.get("intervention_log")
            else None
        ),
        session_state=cached_state,
        buffered_events=cached_events,
        completed_challenges=[
            p["challenge_id"] for p in progress if p["completed"]
        ],
        recent_attempts=recent_attempts,
        peer_percentile=pop_bench.get("percentile") if pop_bench else None,
        population_size=pop_bench.get("population_size") if pop_bench else None,
    )
    log_event(
        logger,
        "stage.prior_info.end",
        user=user_id,
        mastery_keys=list(snapshot.mastery.keys()),
        struggles=len(snapshot.struggles),
        buffered_events=len(snapshot.buffered_events),
    )
    return {
        "prior": snapshot.model_dump(mode="json"),
        "stage_history": [{"stage": "prior_info", "status": "ok"}],
    }
