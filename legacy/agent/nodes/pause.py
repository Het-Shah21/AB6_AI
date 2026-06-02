import logging
from datetime import datetime, timedelta
from typing import Any

from legacy.agent.state import OODAState

logger = logging.getLogger(__name__)


async def pause_node(state: OODAState) -> dict[str, Any]:
    user_id = state.get("user_id", "")
    cycle_count = state.get("cycle_count", 0)
    last_cycle = state.get("last_cycle_timestamp", "")

    logger.info("PAUSE node: user=%s cycle=%d", user_id, cycle_count)

    cooldown_minutes = min(2 ** (cycle_count // 3), 30)
    should_pause = False

    if last_cycle:
        last_time = datetime.fromisoformat(last_cycle)
        elapsed = (datetime.utcnow() - last_time).total_seconds()
        if elapsed < 60:
            should_pause = True

    return {
        "should_pause": should_pause,
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"PAUSE: cooldown={cooldown_minutes}m, "
                    f"should_pause={should_pause}"
                ),
            }
        ],
    }
