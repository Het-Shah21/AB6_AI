import numpy as np


def compute_jerk(angles: list[float], dt: float = 0.01) -> float:
    if len(angles) < 4:
        return 0.0
    arr = np.array(angles, dtype=np.float64)
    vel = np.diff(arr) / dt
    acc = np.diff(vel) / dt
    jerk = np.diff(acc) / dt
    return float(np.mean(np.abs(jerk)))


def compute_smoothness(angles: list[float], dt: float = 0.01) -> float:
    jerk = compute_jerk(angles, dt)
    if jerk == 0:
        return 1.0
    return float(1.0 / (1.0 + np.log1p(jerk)))


def compute_angular_velocity(
    angles: list[float], dt: float = 0.01
) -> list[float]:
    if len(angles) < 2:
        return []
    arr = np.array(angles, dtype=np.float64)
    return (np.diff(arr) / dt).tolist()


def compute_engagement_from_telemetry(
    smoothness: float,
    completion_ratio: float,
    error_rate: float,
    attempt_count: int,
) -> float:
    score = (
        0.3 * smoothness
        + 0.3 * completion_ratio
        - 0.2 * error_rate
        + 0.2 * min(attempt_count / 10.0, 1.0)
    )
    return float(np.clip(score, 0.0, 1.0))
