"""
Zone management module for Pratyaksha.
Handles ROI polygon representations, point-in-polygon containment checks,
expected vs detected infrastructure reconciliation, and rolling median person count smoothing.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np


@dataclass
class Zone:
    """
    Represents a named Region of Interest (ROI) within a camera feed.
    """
    name: str
    polygon: np.ndarray  # Shape (N, 2), int32 pixel coordinates
    expected_infrastructure: Dict[str, int] = field(default_factory=dict)
    smoothing_k: int = 5
    _person_history: deque = field(init=False)

    def __post_init__(self) -> None:
        self._person_history = deque(maxlen=self.smoothing_k)
        if not isinstance(self.polygon, np.ndarray):
            self.polygon = np.array(self.polygon, dtype=np.int32)
        else:
            self.polygon = self.polygon.astype(np.int32)

    def contains_point(self, point: Tuple[float, float]) -> bool:
        """
        Check if an (x, y) coordinate falls inside or on the boundary of the zone polygon.
        """
        pt = (float(point[0]), float(point[1]))
        return cv2.pointPolygonTest(self.polygon, pt, measureDist=False) >= 0

    def update_person_count(self, raw_count: int) -> Tuple[int, int]:
        """
        Add raw person count to rolling window and return (raw_count, smoothed_median_count).
        """
        self._person_history.append(raw_count)
        smoothed = int(round(float(np.median(list(self._person_history)))))
        return raw_count, smoothed

    def evaluate_infrastructure(self, detected_counts: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Reconcile detected infrastructure items against expected sanctioned inventory.
        Status: 'MATCH', 'DEFICIT', or 'SURPLUS'.
        """
        results: List[Dict[str, Any]] = []
        for item, expected in self.expected_infrastructure.items():
            detected = detected_counts.get(item, 0)
            if detected == expected:
                status = "MATCH"
            elif detected < expected:
                status = "DEFICIT"
            else:
                status = "SURPLUS"

            results.append({
                "item": item,
                "expected": expected,
                "detected": detected,
                "status": status,
            })
        return results


class ZoneManager:
    """
    Manages named zones across cameras loaded from configuration.
    """
    def __init__(self, smoothing_k: int = 5) -> None:
        self.smoothing_k = smoothing_k
        self.camera_zones: Dict[str, Dict[str, Zone]] = {}
        self.camera_sources: Dict[str, str] = {}

    @classmethod
    def from_config(cls, config: Dict[str, Any], smoothing_k: Optional[int] = None) -> "ZoneManager":
        """
        Factory method to instantiate ZoneManager from loaded YAML configuration dict.
        """
        k = smoothing_k or config.get("pipeline", {}).get("smoothing_window_k", 5)
        manager = cls(smoothing_k=k)

        cameras_cfg = config.get("cameras", {})
        for cam_id, cam_data in cameras_cfg.items():
            manager.camera_sources[cam_id] = cam_data.get("source", "")
            manager.camera_zones[cam_id] = {}

            zones_cfg = cam_data.get("zones", {})
            for zone_name, zone_info in zones_cfg.items():
                poly_pts = zone_info.get("polygon", [])
                expected_infra = zone_info.get("expected_infrastructure", {})
                zone_obj = Zone(
                    name=zone_name,
                    polygon=np.array(poly_pts, dtype=np.int32),
                    expected_infrastructure=expected_infra,
                    smoothing_k=k,
                )
                manager.camera_zones[cam_id][zone_name] = zone_obj

        return manager

    def get_zones(self, camera_id: str) -> Dict[str, Zone]:
        """
        Retrieve zones for a specific camera ID.
        """
        return self.camera_zones.get(camera_id, {})

    def get_source(self, camera_id: str) -> Optional[str]:
        """
        Retrieve stream / file source path for a camera ID.
        """
        return self.camera_sources.get(camera_id)
