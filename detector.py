"""
Object detection and privacy protection module for Pratyaksha.
Wraps Ultralytics YOLO nano model for person and infrastructure detection,
computes reference anchors for zone containment, and applies strict privacy blurring.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from ultralytics import YOLO


@dataclass
class Detection:
    """
    Standardized detection result for a single identified object.
    """
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    class_id: int
    class_name: str

    @property
    def foot_point(self) -> Tuple[float, float]:
        """
        Bottom-center point (x, y2) of the bounding box.
        Optimal for mapping person presence to ground-plane floor zones.
        """
        x1, _, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, float(y2))

    @property
    def center_point(self) -> Tuple[float, float]:
        """
        Center point of the bounding box.
        Suitable for stationary infrastructure (chairs, workbenches, computers).
        """
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


class ObjectDetector:
    """
    YOLO-based object detector with support for person and infrastructure classes,
    open-vocabulary text prompts (YOLO-World or proxy-mapped zero-shot), custom fine-tuned weights,
    plus privacy-preserving frame anonymization.
    """
    # Mapping for standard COCO weights to domain skilling infrastructure prompts
    DEFAULT_VOCABULARY_MAPPING = {
        "workbench": ["dining table", "bench"],
        "chair": ["chair"],
        "computer": ["laptop", "tv"],
        "laptop": ["laptop"],
        "toolbox": ["suitcase", "backpack", "handbag"],
        "sewing machine": ["refrigerator", "microwave", "toaster", "oven"],
        "lathe": ["boat", "truck", "train"],
        "welding machine": ["refrigerator", "microwave"],
        "drill press": ["parking meter", "fire hydrant"],
    }

    def __init__(
        self,
        model_name: str = "yolov8n.pt",
        confidence_threshold: float = 0.25,
        device: str = "",
        custom_classes: Optional[List[str]] = None,
    ) -> None:
        self.model_name = model_name
        self.conf_thresh = confidence_threshold
        self.device = device if device else None
        self.custom_classes = custom_classes or []

        # Load YOLO model (nano, YOLO-World, or fine-tuned custom weights)
        self.model = YOLO(self.model_name)

        # Apply open-vocabulary classes if model supports YOLO-World set_classes
        if self.custom_classes:
            self.set_vocabulary(self.custom_classes)

    def set_vocabulary(self, classes: List[str]) -> None:
        """
        Dynamically update open-vocabulary text prompts without reloading weights.
        Supports YOLO-World native set_classes, or falls back to prompt mapping.
        """
        self.custom_classes = classes
        if hasattr(self.model, "set_classes") and callable(getattr(self.model, "set_classes")):
            try:
                self.model.set_classes(classes)
            except Exception:
                pass

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Run inference on a single BGR image/frame and return structured detections.
        Normalizes detected classes to match custom open-vocabulary infrastructure classes.
        """
        results = self.model.predict(
            source=frame,
            conf=self.conf_thresh,
            device=self.device,
            verbose=False,
        )

        detections: List[Detection] = []
        if not results:
            return detections

        first_res = results[0]
        names = first_res.names

        # Reverse lookup mapping from proxy class to requested custom class
        proxy_to_custom = {}
        if self.custom_classes:
            for custom_cls in self.custom_classes:
                c_clean = custom_cls.lower().strip()
                proxy_to_custom[c_clean] = custom_cls
                if c_clean in self.DEFAULT_VOCABULARY_MAPPING:
                    for proxy in self.DEFAULT_VOCABULARY_MAPPING[c_clean]:
                        proxy_to_custom[proxy.lower().strip()] = custom_cls

        for box in first_res.boxes:
            xyxy = box.xyxy[0].cpu().numpy().astype(int)
            conf = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            cls_name = names.get(cls_id, str(cls_id))

            # Normalize class name to configured custom vocabulary if applicable
            mapped_name = cls_name
            if self.custom_classes:
                c_lower = cls_name.lower().strip()
                if c_lower in proxy_to_custom:
                    mapped_name = proxy_to_custom[c_lower]

            x1, y1, x2, y2 = xyxy
            detections.append(
                Detection(
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    confidence=conf,
                    class_id=cls_id,
                    class_name=mapped_name,
                )
            )

        return detections

    @staticmethod
    def apply_privacy_blur(
        frame: np.ndarray,
        person_detections: List[Detection],
        kernel_size: int = 35,
    ) -> np.ndarray:
        """
        Preserve privacy by heavily blurring all detected persons (faces and bodies).
        No recognizable facial or individual features remain.
        """
        anonymized = frame.copy()
        h, w = anonymized.shape[:2]

        # Ensure kernel size is positive and odd
        ksize = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
        ksize = max(9, ksize)

        for det in person_detections:
            x1, y1, x2, y2 = det.bbox
            # Clamp coordinates to frame boundaries
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))

            if x2 <= x1 or y2 <= y1:
                continue

            person_roi = anonymized[y1:y2, x1:x2]
            if person_roi.size == 0:
                continue

            # Heavy Gaussian blur to eradicate identifying details
            blurred_roi = cv2.GaussianBlur(person_roi, (ksize, ksize), 0)
            anonymized[y1:y2, x1:x2] = blurred_roi

            # Draw a subtle anonymized boundary marker
            cv2.rectangle(anonymized, (x1, y1), (x2, y2), (200, 200, 200), 1, cv2.LINE_AA)

        return anonymized

    @staticmethod
    def annotate_frame(
        frame: np.ndarray,
        detections: List[Detection],
        zones: Dict[str, Any],
        class_mapping: Dict[str, List[str]],
        blur_persons: bool = True,
        blur_kernel_size: int = 35,
    ) -> np.ndarray:
        """
        Generate diagnostic visualization frame:
        - Outlines zones with clean labels
        - Blurs all detected persons for privacy
        - Boxes detected infrastructure with item tags
        """
        # Step 1: Privacy blur for persons
        person_dets = [d for d in detections if d.class_name == "person"]
        if blur_persons:
            annotated = ObjectDetector.apply_privacy_blur(frame, person_dets, blur_kernel_size)
        else:
            annotated = frame.copy()

        # Step 2: Draw zone polygons with semi-transparent overlay
        overlay = annotated.copy()
        for zone_name, zone in zones.items():
            pts = zone.polygon.reshape((-1, 1, 2))
            cv2.fillPoly(overlay, [pts], (240, 215, 140))
            cv2.polylines(annotated, [pts], isClosed=True, color=(255, 165, 0), thickness=2)

            # Draw zone title tag
            if len(zone.polygon) > 0:
                tag_x, tag_y = zone.polygon[0]
                cv2.putText(
                    annotated,
                    f"Zone: {zone_name}",
                    (int(tag_x), max(20, int(tag_y) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

        cv2.addWeighted(overlay, 0.25, annotated, 0.75, 0, annotated)

        # Step 3: Draw infrastructure boxes
        for det in detections:
            if det.class_name == "person":
                continue

            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 128), 2, cv2.LINE_AA)
            label = f"{det.class_name} {det.confidence:.2f}"
            cv2.putText(
                annotated,
                label,
                (x1, max(15, y1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 128),
                1,
                cv2.LINE_AA,
            )

        return annotated
