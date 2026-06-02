import logging
from datetime import datetime
from typing import Any

from legacy.agent.state import OODAState
from legacy.ingestion.aggregator import TelemetryAggregator

logger = logging.getLogger(__name__)

_telemetry_aggregator = TelemetryAggregator()


async def observe_node(state: OODAState) -> dict[str, Any]:
    user_id = state.get("user_id", "")
    logger.info("OBSERVE node: user=%s cycle=%d", user_id, state.get("cycle_count", 0))

    raw_events = state.get("raw_events", [])[-100:]
    telemetry_window = _telemetry_aggregator.aggregate(user_id)

    time_on_page = 0.0
    attempt_velocity = 0.0
    error_count = 0
    total_attempts = 0
    video_engagement = 0.5
    code_iterations = 0

    for event in raw_events:
        event_type = event.get("event_type", "")
        if event_type == "end_attempt":
            total_attempts += 1
            if not event.get("is_correct", True):
                error_count += 1
        elif event_type == "run_code":
            code_iterations += 1

    error_rate = error_count / max(total_attempts, 1)

    derived_signals = {
        "time_on_page": time_on_page,
        "attempt_velocity": attempt_velocity,
        "error_rate": error_rate,
        "total_attempts": total_attempts,
        "video_engagement": video_engagement,
        "code_iteration_count": code_iterations,
        "telemetry_smoothness": telemetry_window.get("2m", {}).get(
            "smoothness", 0.5
        ),
        "observed_at": datetime.utcnow().isoformat(),
    }

    return {
        "raw_events": raw_events,
        "telemetry_window": telemetry_window,
        "messages": [
            {
                "role": "assistant",
                "content": f"OBSERVE complete: {total_attempts} attempts, "
                f"{error_rate:.0%} error rate",
            }
        ],
        "_derived_signals": derived_signals,
    }
