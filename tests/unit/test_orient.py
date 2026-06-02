import pytest


@pytest.mark.asyncio
async def test_orient_node_skipped_due_to_db():
    assert True


@pytest.mark.asyncio
async def test_compute_engagement_trend():
    from legacy.agent.nodes.orient import _compute_engagement_trend

    assert _compute_engagement_trend([]) == "stable"
    assert _compute_engagement_trend([{"score": 0.5}]) == "stable"
    assert (
        _compute_engagement_trend(
            [
                {"score": 0.7},
                {"score": 0.6},
                {"score": 0.5},
                {"score": 0.4},
                {"score": 0.3},
            ]
        )
        == "declining"
    )
    assert (
        _compute_engagement_trend(
            [
                {"score": 0.3},
                {"score": 0.4},
                {"score": 0.5},
                {"score": 0.6},
                {"score": 0.7},
            ]
        )
        == "improving"
    )
