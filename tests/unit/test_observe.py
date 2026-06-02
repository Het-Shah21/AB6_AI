import pytest

from legacy.agent.nodes.observe import observe_node


@pytest.mark.asyncio
async def test_observe_node_basic():
    state = {
        "user_id": "test-user",
        "session_id": "test-session",
        "raw_events": [
            {
                "event_type": "end_attempt",
                "is_correct": True,
                "score": 0.9,
            },
            {
                "event_type": "end_attempt",
                "is_correct": False,
                "score": 0.3,
            },
            {"event_type": "run_code"},
        ],
        "cycle_count": 0,
    }
    result = await observe_node(state)
    assert "raw_events" in result
    assert "telemetry_window" in result
    assert "messages" in result
    assert len(result["messages"]) > 0
