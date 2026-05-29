import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from src.config.settings import get_settings


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def sample_observation_event():
    return {
        "user_id": "test-user-1",
        "session_id": "test-session-1",
        "event_type": "end_attempt",
        "action": "submit",
        "page": "/challenge/1",
        "challenge_id": "challenge-1",
        "score": 0.8,
        "is_correct": True,
        "metadata": {"time_spent": 120},
        "timestamp": "2026-05-29T12:00:00Z",
    }


@pytest_asyncio.fixture
async def sample_telemetry_event():
    return {
        "user_id": "test-user-1",
        "session_id": "test-session-1",
        "joint_angles": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        "imu_data": {
            "accel_x": 0.0,
            "accel_y": 9.81,
            "accel_z": 0.0,
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,
        },
        "encoder_data": [100, 200, 300],
        "timestamp": "2026-05-29T12:00:01Z",
    }


@pytest_asyncio.fixture
async def sample_learner_profile():
    return {
        "mastery_map": {
            "kinematics.forward.dh_parameters": {
                "mastery": 0.85,
                "attempts": 5,
            },
            "kinematics.inverse.jacobian": {
                "mastery": 0.3,
                "attempts": 12,
            },
        },
        "learning_style": {"prefers": "visual", "reading_speed": "fast"},
        "engagement_history": [
            {"score": 0.7, "context": "challenge_1"},
            {"score": 0.5, "context": "challenge_2"},
            {"score": 0.4, "context": "challenge_3"},
        ],
        "struggle_patterns": {
            "kinematics.inverse.jacobian": {
                "attempts": 12,
                "avg_score": 0.35,
                "common_errors": ["jacobian_transpose"],
            }
        },
    }
