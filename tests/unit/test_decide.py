import pytest

from src.agent.nodes.decide import decide_router, _segment_learner


def test_decide_router_pause():
    state = {"should_pause": True}
    assert decide_router(state) == "pause"


def test_decide_router_act():
    state = {"should_pause": False}
    assert decide_router(state) == "act"


def test_segment_learner():
    profile = {
        "mastery_map": {
            "a": {"mastery": 0.8},
            "b": {"mastery": 0.4},
        },
        "learning_style": {"prefers": "visual"},
        "engagement_history": [{"score": 0.5}, {"score": 0.6}],
    }
    segment = _segment_learner(profile)
    assert segment["mastery_range"] == [0.4, 0.8]
    assert segment["learning_style"] == "visual"
    assert segment["struggle_count_gte"] == 2
