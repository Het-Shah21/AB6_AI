"""Stage 3 — ANALYZE.

Pattern detection on the observed event stream. Heuristic-first, but
pluggable for LLM-assisted analysis. Produces `AnalyzedPattern`.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from typing import Any

from src.mentor.observability import get_logger, log_event
from src.mentor.state import AnalyzedPattern, MentorState, ObservedSignals

logger = get_logger(__name__)


async def run(state: MentorState) -> dict[str, Any]:
    user_id: str = state["user_id"]
    cycle_id: uuid.UUID = state["cycle_id"]
    log_event(logger, "stage.analyze.start", user=user_id, cycle=str(cycle_id))

    observed: ObservedSignals = ObservedSignals.model_validate(state["observed"])
    events = observed.events

    failed_runs_by_challenge: dict[str, int] = defaultdict(int)
    repeated_attempts_by_challenge: dict[str, int] = defaultdict(int)
    score_trend_by_challenge: dict[str, list[float]] = defaultdict(list)
    hint_seeks_by_concept: dict[str, int] = defaultdict(int)
    inactivity_seconds: float = 0.0
    last_ts: float | None = None
    nav_count = 0
    submit_count = 0
    run_count = 0

    for e in events:
        if e.timestamp is not None and last_ts is not None:
            inactivity_seconds = max(inactivity_seconds, e.timestamp - last_ts)
        if e.timestamp is not None:
            last_ts = e.timestamp

        if e.event_type in {"code_run", "code_execution"}:
            run_count += 1
            if e.is_correct is False:
                failed_runs_by_challenge[e.challenge_id or "_"] += 1
            if e.score is not None:
                score_trend_by_challenge[e.challenge_id or "_"].append(float(e.score))
        if e.event_type in {"challenge_submit", "submission"}:
            submit_count += 1
        if e.event_type in {"page_navigate", "navigation", "tab_switch"}:
            nav_count += 1
        if e.event_type in {"hint_request", "show_hint", "ask_help"}:
            hint_seeks_by_concept[e.challenge_id or "_"] += 1
        if e.attempt_no and e.attempt_no > 1:
            repeated_attempts_by_challenge[e.challenge_id or "_"] += 1

    struggle_challenges = [
        cid
        for cid, fails in failed_runs_by_challenge.items()
        if fails >= 2 or repeated_attempts_by_challenge.get(cid, 0) >= 2
    ]

    declining = [
        cid
        for cid, scores in score_trend_by_challenge.items()
        if len(scores) >= 3
        and (sum(scores[-3:]) / 3.0) < (sum(scores[:3]) / max(1, len(scores[:3])))
    ]

    disengaged = inactivity_seconds > 300 or (run_count == 0 and submit_count == 0 and nav_count > 4)

    speed_drift = nav_count >= 5 and submit_count == 0

    pattern = AnalyzedPattern(
        struggle_challenges=struggle_challenges,
        hint_seeks=sum(hint_seeks_by_concept.values()),
        declining_challenges=declining,
        is_disengaged=disengaged,
        is_speed_drifting=speed_drift,
        inactivity_seconds=inactivity_seconds,
        failed_runs=failed_runs_by_challenge,
        repeated_attempts=repeated_attempts_by_challenge,
        score_trend=score_trend_by_challenge,
    )
    log_event(
        logger,
        "stage.analyze.end",
        user=user_id,
        struggle=len(struggle_challenges),
        hints=pattern.hint_seeks,
        disengaged=disengaged,
    )
    return {
        "analyzed": pattern.model_dump(mode="json"),
        "stage_history": [{"stage": "analyze", "status": "ok"}],
    }
