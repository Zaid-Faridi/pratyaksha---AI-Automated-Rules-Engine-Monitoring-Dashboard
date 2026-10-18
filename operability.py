"""
Apparent Operability Assessment Module for Pratyaksha.
Evaluates physical state and apparent operability of sanctioned skilling equipment:
- Status classifications: 'operational', 'uncertain', 'non_operational', 'missing'
- Explainable, lightweight computer vision heuristics per equipment type:
  * Computers/Monitors: Screen-on luminance & variance, trainee typing proximity
  * Machinery (Lathe, Welding, Sewing, Drill Press): Power LED indicator, trainee proximity, tool/material presence, covered/stacked tarp detection
  * Seating & Workbenches: Blocked/piled by stored boxes or materials
- Temporal aggregation over consecutive sample windows
- Transparent disclaimer: Operability is a heuristic indication, not an electrical diagnostic.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from detector import Detection


OPERABILITY_DISCLAIMER = (
    "DISCLAIMER: Apparent operability is inferred heuristically from visual interaction, "
    "screen luminescence, and physical clearance. It serves as an audit signal, not an electrical diagnostic."
)


@dataclass
class OperabilityAssessment:
    """Detailed explainable assessment for a single piece of equipment."""
    item: str
    status: str  # 'operational', 'uncertain', 'non_operational', 'missing'
    signals: Dict[str, Any]
    explanation: str
    confidence: float = 0.85

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item": self.item,
            "status": self.status,
            "signals": self.signals,
            "explanation": self.explanation,
            "confidence": round(self.confidence, 2),
            "disclaimer": OPERABILITY_DISCLAIMER,
        }


class OperabilityEvaluator:
    """
    Computes explainable visual operability heuristics per equipment item.
    """

    @staticmethod
    def evaluate_computer(
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        has_person_proximate: bool = False,
    ) -> OperabilityAssessment:
        """
        Assess screen-on state and user presence for computers and monitors.
        """
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return OperabilityAssessment(
                item="computer",
                status="uncertain",
                signals={"error": "invalid_roi"},
                explanation="Computer bounding box coordinates invalid",
            )

        roi = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi

        # Calculate luminance and color variance
        mean_brightness = float(np.mean(gray))
        contrast_std = float(np.std(gray))

        # Check color channels difference (screens have colorful displays)
        color_variance = 0.0
        if len(roi.shape) == 3:
            b, g, r = cv2.split(roi)
            color_variance = float(np.std(r.astype(float) - b.astype(float)))

        is_screen_illuminated = mean_brightness > 55.0 and (contrast_std > 22.0 or color_variance > 14.0)

        signals = {
            "mean_brightness": round(mean_brightness, 1),
            "contrast_variance": round(contrast_std, 1),
            "color_variance": round(color_variance, 1),
            "screen_illuminated": is_screen_illuminated,
            "screen_on": is_screen_illuminated,
            "trainee_proximate": has_person_proximate,
        }

        if is_screen_illuminated and has_person_proximate:
            return OperabilityAssessment(
                item="computer",
                status="operational",
                signals=signals,
                explanation="Active illuminated display with trainee seated/operating at station.",
                confidence=0.92,
            )
        elif is_screen_illuminated:
            return OperabilityAssessment(
                item="computer",
                status="operational",
                signals=signals,
                explanation="Display screen active and powered on in lab.",
                confidence=0.88,
            )
        elif not is_screen_illuminated and not has_person_proximate and mean_brightness < 30.0:
            return OperabilityAssessment(
                item="computer",
                status="non_operational",
                signals=signals,
                explanation="Display screen completely dark with zero user interaction detected.",
                confidence=0.80,
            )
        else:
            return OperabilityAssessment(
                item="computer",
                status="uncertain",
                signals=signals,
                explanation="Screen state standby or ambiguous lighting; further samples needed.",
                confidence=0.65,
            )

    @staticmethod
    def evaluate_machine(
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        item_name: str,
        has_person_proximate: bool = False,
        other_detections: Optional[List[Detection]] = None,
    ) -> OperabilityAssessment:
        """
        Assess industrial machinery (lathe, welding, sewing, drill press):
        - Power indicator / pilot LED detection
        - Trainee proximity & operation
        - Covered/stacked with cloth or storage items
        """
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return OperabilityAssessment(
                item=item_name,
                status="uncertain",
                signals={"error": "invalid_roi"},
                explanation="Machine bounding box coordinates invalid",
            )

        roi = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi

        # Check for covered / draped tarp (low texture gradient variance across center)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_covered = laplacian_var < 18.0 and float(np.std(gray)) < 15.0

        # Pilot light / LED spot detection: look for concentrated peak highlights in upper 40%
        upper_roi = gray[: int(gray.shape[0] * 0.4), :]
        has_bright_led = bool(upper_roi.size > 0 and np.max(upper_roi) >= 240 and np.sum(upper_roi >= 235) <= 150)

        # Tool or material presence nearby
        tool_nearby = False
        if other_detections:
            mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            for d in other_detections:
                if d.class_name in ("toolbox", "laptop", "bottle"):
                    dx = d.center_point[0] - mx
                    dy = d.center_point[1] - my
                    if (dx * dx + dy * dy) ** 0.5 < max(x2 - x1, y2 - y1) * 1.5:
                        tool_nearby = True
                        break

        signals = {
            "laplacian_texture_variance": round(laplacian_var, 1),
            "is_covered_with_tarp": is_covered,
            "pilot_led_active": has_bright_led,
            "trainee_proximate": has_person_proximate,
            "tool_presence": tool_nearby,
        }

        if is_covered:
            return OperabilityAssessment(
                item=item_name,
                status="non_operational",
                signals=signals,
                explanation="Machine appears draped, covered, or obstructed by storage materials.",
                confidence=0.88,
            )
        elif has_person_proximate or (has_bright_led and tool_nearby):
            return OperabilityAssessment(
                item=item_name,
                status="operational",
                signals=signals,
                explanation="Trainee actively operating station with clear tooling access.",
                confidence=0.90,
            )
        elif not has_person_proximate and not has_bright_led:
            return OperabilityAssessment(
                item=item_name,
                status="uncertain",
                signals=signals,
                explanation="Machine clear and uncovered, but currently idle without proximate operator.",
                confidence=0.70,
            )
        else:
            return OperabilityAssessment(
                item=item_name,
                status="operational",
                signals=signals,
                explanation="Machine uncovered with power/pilot indicator active.",
                confidence=0.82,
            )

    @staticmethod
    def evaluate_seating_or_bench(
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        item_name: str,
        other_detections: Optional[List[Detection]] = None,
    ) -> OperabilityAssessment:
        """
        Assess seating (chair/bench/workbench) to confirm whether usable or blocked by boxes.
        """
        x1, y1, x2, y2 = bbox
        blocked_by_boxes = False
        if other_detections:
            for d in other_detections:
                if d.class_name in ("toolbox", "suitcase", "backpack"):
                    # Check box intersection over chair area
                    ox1, oy1, ox2, oy2 = d.bbox
                    inter_x1, inter_y1 = max(x1, ox1), max(y1, oy1)
                    inter_x2, inter_y2 = min(x2, ox2), min(y2, oy2)
                    if inter_x2 > inter_x1 and inter_y2 > inter_y1:
                        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
                        chair_area = max(1, (x2 - x1) * (y2 - y1))
                        if inter_area / float(chair_area) > 0.35:
                            blocked_by_boxes = True
                            break

        signals = {
            "blocked_by_boxes_or_materials": blocked_by_boxes,
            "clear_seating_access": not blocked_by_boxes,
        }

        if blocked_by_boxes:
            return OperabilityAssessment(
                item=item_name,
                status="non_operational",
                signals=signals,
                explanation="Seating station blocked by stacked toolboxes or storage items.",
                confidence=0.85,
            )
        else:
            return OperabilityAssessment(
                item=item_name,
                status="operational",
                signals=signals,
                explanation="Station clear and ready for trainee occupancy.",
                confidence=0.90,
            )


class OperabilityHistoryTracker:
    """
    Combines item operability signals over rolling time windows.
    Avoids false alerts on momentary pauses, requiring M consecutive non-operational samples.
    """

    def __init__(self, history_len: int = 5, consecutive_threshold: int = 3) -> None:
        self.history_len = history_len
        self.consecutive_threshold = consecutive_threshold
        # Key: (camera_id, zone, item) -> deque of recent statuses
        self._history: Dict[Tuple[str, str, str], deque] = {}

    def update(
        self,
        camera_id: str,
        zone: str,
        item: str,
        current_status: str,
    ) -> Tuple[str, int]:
        """
        Record current status in rolling window.
        Returns (effective_status, consecutive_inactive_count).
        """
        key = (camera_id, zone, item)
        if key not in self._history:
            self._history[key] = deque(maxlen=self.history_len)

        hist = self._history[key]
        hist.append(current_status)

        # Count consecutive non_operational from the right
        consecutive_non_op = 0
        for s in reversed(hist):
            if s == "non_operational":
                consecutive_non_op += 1
            else:
                break

        # Solidify status to non_operational only when consecutive threshold met
        if consecutive_non_op >= self.consecutive_threshold:
            effective_status = "non_operational"
        elif current_status == "operational":
            effective_status = "operational"
        elif current_status == "non_operational":
            effective_status = "uncertain"
        else:
            effective_status = current_status

        return effective_status, consecutive_non_op


operability_tracker = OperabilityHistoryTracker()
