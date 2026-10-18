"""
Frame Quality Gating Module for Pratyaksha.
Evaluates per-frame visual health to prevent false attendance deficits and equipment gaps:
- Brightness: Mean luminance (detects severe darkness or blinding glare)
- Blur: Variance of Laplacian (detects out-of-focus or motion blurred frames)
- Contrast: RMS intensity standard deviation (detects washed-out feeds)
- Camera Obstructed / Scene Shift: Structural correlation against reference scene image
- Exclusion Gating: Flags samples as 'unreliable' so rules engine ignores degraded frames
- Health Alerting: Tracks consecutive degraded frames to raise POOR_CAMERA_QUALITY alerts
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np


@dataclass
class QualityThresholds:
    """Configurable quality thresholds."""
    min_brightness: float = 35.0
    max_brightness: float = 230.0
    min_blur_laplacian: float = 45.0
    min_contrast: float = 20.0
    min_scene_correlation: float = 0.25
    consecutive_unreliable_alert_threshold: int = 3


@dataclass
class FrameQualityResult:
    """Structured quality assessment for a single video frame."""
    is_reliable: bool
    quality_score: float  # 0 to 100
    brightness: float
    blur_laplacian: float
    contrast: float
    scene_similarity: float
    is_obstructed: bool
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_reliable": self.is_reliable,
            "quality_score": round(self.quality_score, 1),
            "brightness": round(self.brightness, 1),
            "blur_laplacian": round(self.blur_laplacian, 1),
            "contrast": round(self.contrast, 1),
            "scene_similarity": round(self.scene_similarity, 2),
            "is_obstructed": self.is_obstructed,
            "issues": self.issues,
        }


class FrameQualityEvaluator:
    """
    Computes visual quality metrics and manages reference frames per camera.
    """

    def __init__(self, thresholds: Optional[QualityThresholds] = None) -> None:
        self.thresholds = thresholds or QualityThresholds()
        # Stored reference scene images per camera (downscaled thumbnail)
        self.reference_frames: Dict[str, np.ndarray] = {}
        # Consecutive unreliable sample tracking per camera
        self.consecutive_unreliable: Dict[str, int] = {}

    def set_reference_frame(self, camera_id: str, frame: np.ndarray) -> None:
        """Store a reference scene baseline for tamper / obstruction comparison."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        # Downscale to 160x90 for fast, robust cross-correlation
        thumb = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
        self.reference_frames[camera_id] = thumb

    def evaluate_frame(
        self,
        frame: np.ndarray,
        camera_id: Optional[str] = None,
        custom_ref: Optional[np.ndarray] = None,
    ) -> FrameQualityResult:
        """
        Evaluate frame health against quality gates.
        """
        if frame is None or frame.size == 0:
            return FrameQualityResult(
                is_reliable=False,
                quality_score=0.0,
                brightness=0.0,
                blur_laplacian=0.0,
                contrast=0.0,
                scene_similarity=0.0,
                is_obstructed=True,
                issues=["EMPTY_FRAME"],
            )

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        issues: List[str] = []

        # 1. Brightness Check
        brightness = float(np.mean(gray))
        if brightness < self.thresholds.min_brightness:
            issues.append("TOO_DARK")
        elif brightness > self.thresholds.max_brightness:
            issues.append("BLINDING_GLARE")

        # 2. Blur Check (Variance of Laplacian)
        blur_laplacian = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if blur_laplacian < self.thresholds.min_blur_laplacian:
            issues.append("BLURRY_OUT_OF_FOCUS")

        # 3. Contrast Check (Standard Deviation)
        contrast = float(np.std(gray))
        if contrast < self.thresholds.min_contrast:
            issues.append("LOW_CONTRAST")

        # 4. Obstruction / Movement Check vs Reference Frame
        ref = custom_ref
        if ref is None and camera_id and camera_id in self.reference_frames:
            ref = self.reference_frames[camera_id]

        scene_similarity = 1.0
        is_obstructed = False

        if ref is not None:
            ref_gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY) if len(ref.shape) == 3 else ref
            curr_thumb = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
            ref_thumb = cv2.resize(ref_gray, (160, 90), interpolation=cv2.INTER_AREA)

            # Normalized 2D cross-correlation
            res = cv2.matchTemplate(curr_thumb, ref_thumb, cv2.TM_CCOEFF_NORMED)
            scene_similarity = float(np.max(res))

            if scene_similarity < self.thresholds.min_scene_correlation:
                issues.append("CAMERA_OBSTRUCTED_OR_MOVED")
                is_obstructed = True
        else:
            # Check for lens covered by solid tape or cloth (uniform standard deviation < 8.0)
            if contrast < 8.0:
                issues.append("CAMERA_OBSTRUCTED")
                is_obstructed = True
                scene_similarity = 0.0

        is_reliable = len(issues) == 0

        # Update consecutive tracking if camera_id provided
        if camera_id:
            if not is_reliable:
                self.consecutive_unreliable[camera_id] = self.consecutive_unreliable.get(camera_id, 0) + 1
            else:
                self.consecutive_unreliable[camera_id] = 0
                # Auto-initialize reference frame if not yet set and frame is crystal clear
                if camera_id not in self.reference_frames and is_reliable:
                    self.set_reference_frame(camera_id, frame)

        # Composite quality score (0 to 100)
        score_components = [
            min(1.0, max(0.0, (brightness - 15) / 100.0)),
            min(1.0, max(0.0, blur_laplacian / 150.0)),
            min(1.0, max(0.0, contrast / 50.0)),
            min(1.0, max(0.0, scene_similarity)),
        ]
        quality_score = max(5.0, sum(score_components) * 25.0) if not is_obstructed else 5.0
        if not is_reliable:
            quality_score = min(quality_score, 45.0)

        return FrameQualityResult(
            is_reliable=is_reliable,
            quality_score=quality_score,
            brightness=brightness,
            blur_laplacian=blur_laplacian,
            contrast=contrast,
            scene_similarity=scene_similarity,
            is_obstructed=is_obstructed,
            issues=issues,
        )


quality_evaluator = FrameQualityEvaluator()


def evaluate_frame_quality(frame: np.ndarray, camera_id: Optional[str] = None) -> FrameQualityResult:
    """Convenience helper to evaluate frame quality."""
    return quality_evaluator.evaluate_frame(frame, camera_id=camera_id)
