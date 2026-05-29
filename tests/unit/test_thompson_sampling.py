import numpy as np
import pytest

from src.intervention.selector import segment_learner
from src.db.repositories.wisdom_repo import WisdomRepo


def test_segment_learner_empty():
    profile = {}
    segment = segment_learner(profile)
    assert "mastery_range" in segment
    assert "learning_style" in segment
    assert "struggle_count_gte" in segment


def test_segment_learner_with_data():
    profile = {
        "mastery_map": {
            "a": {"mastery": 0.9},
            "b": {"mastery": 0.7},
        },
        "learning_style": {"prefers": "kinesthetic"},
        "engagement_history": [{"score": 0.8}],
    }
    segment = segment_learner(profile)
    assert segment["mastery_range"] == [0.6, 1.0]
    assert segment["learning_style"] == "kinesthetic"


def test_beta_distribution_sampling():
    samples = [np.random.beta(10, 2) for _ in range(1000)]
    avg = np.mean(samples)
    assert 0.7 < avg < 0.9

    samples_low = [np.random.beta(2, 10) for _ in range(1000)]
    avg_low = np.mean(samples_low)
    assert 0.1 < avg_low < 0.3
