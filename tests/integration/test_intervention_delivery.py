import pytest

from src.agent.nodes.act import _build_intervention_content
from src.intervention.effectiveness import calibrate_difficulty


@pytest.mark.asyncio
async def test_calibrate_difficulty():
    challenge = {"difficulty": 0.7}
    concept = {"difficulty": 0.5}
    result = calibrate_difficulty(challenge, concept)
    assert result == 0.6


@pytest.mark.asyncio
async def test_calibrate_difficulty_no_concept():
    challenge = {"difficulty": 0.7}
    result = calibrate_difficulty(challenge, None)
    assert result == 0.6


@pytest.mark.asyncio
async def test_intervention_content_generation():
    selected = {
        "type": "video_recommendation",
        "concept_id": "kinematics.forward.dh_parameters",
        "rationale": "Video will help visualize DH parameters",
        "priority": "medium",
    }
    content = _build_intervention_content(
        "video_recommendation",
        "kinematics.forward.dh_parameters",
        selected,
    )
    assert "body" in content
    assert "title" in content
