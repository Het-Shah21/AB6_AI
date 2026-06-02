import pytest

from legacy.agent.nodes.act import _build_intervention_content


def test_build_concept_explanation():
    selected = {
        "type": "concept_explanation",
        "concept_id": "kinematics.forward.dh_parameters",
        "rationale": "Learner struggles with DH parameters",
        "priority": "high",
    }
    content = _build_intervention_content(
        "concept_explanation", "kinematics.forward.dh_parameters", selected
    )
    assert "body" in content
    assert len(content["body"]) > 0


def test_build_encouragement():
    selected = {
        "type": "encouragement",
        "concept_id": "general",
        "rationale": "Engagement dropping",
        "priority": "medium",
    }
    content = _build_intervention_content(
        "encouragement", "general", selected
    )
    assert "body" in content
    assert "progress" in content["body"].lower()
