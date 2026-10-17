"""
Edge Inference Runtime for Pratyaksha.
Wraps ONNX Runtime on CPU and Ultralytics YOLO with support for dynamic input sizing (320, 480, 640)
and profile-aware resource conservation.
"""

from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np
from ultralytics import YOLO

# Re-use Phase 1 detection types without duplication
from detector import Detection, ObjectDetector


class EdgeDetectorRuntime:
    """
    Optimized inference runtime supporting both ONNX Runtime (CPU) and PyTorch YOLO nano.
    """
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        onnx_path: str = "yolov8n.onnx",
        prefer_onnx: bool = True,
        confidence_threshold: float = 0.25,
    ) -> None:
        self.conf_thresh = confidence_threshold
        self.onnx_path = onnx_path
        self.model_path = model_path
        self.is_onnx = False

        # Attempt to load ONNX model if requested and available
        if prefer_onnx and Path(onnx_path).exists():
            try:
                print(f"[EDGE RUNTIME] Loading ONNX model from '{onnx_path}' (CPU)...")
                self.model = YOLO(onnx_path, task="detect")
                self.is_onnx = True
                print("[EDGE RUNTIME] Successfully initialized ONNX Runtime model.")
            except Exception as e:
                print(f"[EDGE RUNTIME] Fallback to PyTorch model: {e}")
                self.model = YOLO(model_path)
                self.is_onnx = False
        else:
            print(f"[EDGE RUNTIME] Loading standard YOLO model from '{model_path}'...")
            self.model = YOLO(model_path)
            self.is_onnx = False

    def detect(self, frame: np.ndarray, imgsz: int = 640) -> List[Detection]:
        """
        Run inference with dynamic profile input resolution (320, 480, 640).
        """
        results = self.model.predict(
            source=frame,
            conf=self.conf_thresh,
            imgsz=imgsz,
            device="cpu",
            verbose=False,
        )

        detections: List[Detection] = []
        if not results:
            return detections

        first_res = results[0]
        names = first_res.names

        for box in first_res.boxes:
            xyxy = box.xyxy[0].cpu().numpy().astype(int)
            conf = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            cls_name = names.get(cls_id, str(cls_id))

            x1, y1, x2, y2 = xyxy
            detections.append(
                Detection(
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    confidence=conf,
                    class_id=cls_id,
                    class_name=cls_name,
                )
            )

        return detections
