import pytest


@pytest.mark.asyncio
async def test_ooda_cycle_state_transitions():
    from src.agent.state import OODAState
    state = OODAState(
        user_id="test-user",
        session_id="test-session",
        raw_events=[],
        telemetry_window={},
        learner_profile={},
        concept_state={},
        diagnosed_struggles=[],
        engagement_score=0.5,
        selected_intervention=None,
        intervention_candidates=[],
        exploration_flag=False,
        intervention_delivered=None,
        delivery_channel="",
        cycle_count=0,
        last_cycle_timestamp="",
        should_pause=False,
        messages=[],
    )
    assert state["user_id"] == "test-user"
    assert state["cycle_count"] == 0


@pytest.mark.asyncio
async def test_agent_graph_structure():
    from src.agent.graph import build_ooda_graph
    graph = build_ooda_graph()
    assert graph is not None
    nodes = {n for n in graph.nodes}
    assert "observe" in nodes
    assert "orient" in nodes
    assert "decide" in nodes
    assert "act" in nodes
    assert "pause" in nodes
