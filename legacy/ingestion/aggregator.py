import logging
from collections import defaultdict
from typing import Any

import numpy as np

from src.shared.telemetry_math import (
    compute_smoothness,
    compute_engagement_from_telemetry,
)

logger = logging.getLogger(__name__)


class TelemetryAggregator:
    def __init__(self):
        self._windows: dict[str, dict[str, list[dict[str, Any]]]] = (
            defaultdict(lambda: {"30s": [], "2m": [], "5m": []})
        )

    def add_data(
        self, user_id: str, telemetry: dict[str, Any]
    ) -> None:
        for window_key in self._windows[user_id]:
            self._windows[user_id][window_key].append(telemetry)

    def aggregate(
        self, user_id: str
    ) -> dict[str, Any]:
        windows = self._windows.get(user_id, {})
        result = {}

        for window_key, data in windows.items():
            if not data:
                continue
            joint_angles = [
                d.get("joint_angles", [])
                for d in data
                if d.get("joint_angles")
            ]
            all_angles = [
                a
                for angles in joint_angles
                for a in (angles if isinstance(angles, list) else [angles])
            ]
            smoothness = (
                compute_smoothness(all_angles) if all_angles else 1.0
            )
            imu_readings = [
                d.get("imu_data", {})
                for d in data
                if d.get("imu_data")
            ]

            result[window_key] = {
                "smoothness": smoothness,
                "imu_samples": len(imu_readings),
                "joint_samples": len(joint_angles),
            }

        return result

    def compute_engagement(
        self,
        user_id: str,
        completion_ratio: float = 0.5,
        error_rate: float = 0.0,
        attempt_count: int = 1,
    ) -> float:
        agg = self.aggregate(user_id)
        smoothness = agg.get("2m", {}).get("smoothness", 0.5)
        return compute_engagement_from_telemetry(
            smoothness=smoothness,
            completion_ratio=completion_ratio,
            error_rate=error_rate,
            attempt_count=attempt_count,
        )

    def clear(self, user_id: str) -> None:
        self._windows.pop(user_id, None)
