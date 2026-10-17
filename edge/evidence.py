"""
Privacy-Preserving Evidence Thumbnail Generator for Pratyaksha Edge.
Produces ultra-compact, heavily blurred diagnostic frames strictly upon local alert conditions.
Enforces:
1. All detected persons blurred before persistence (zero facial or individual data saved).
2. Maximum width <= 320 px.
3. JPEG quality ~50 for minimal byte footprint (typically 4-8 KB).
"""

import base64
from pathlib import Path
from typing import List, Optional, Tuple
import cv2
import numpy as np

from detector import Detection, ObjectDetector


class EvidenceGenerator:
    """
    Creates lightweight, privacy-guaranteed evidence thumbnails.
    """
    @staticmethod
    def create_thumbnail(
        frame: np.ndarray,
        detections: List[Detection],
        event_id: str,
        output_dir: str = "edge/data/evidence",
        max_width: int = 320,
        jpeg_quality: int = 50,
        blur_kernel_size: int = 35,
    ) -> Optional[Tuple[str, int]]:
        """
        Produce a downscaled, privacy-blurred thumbnail and save to disk.
        Returns (saved_file_path, byte_size) or None on failure.
        """
        if frame is None or frame.size == 0:
            return None

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        target_file = out_path / f"{event_id}.jpg"

        # 1. Filter all person detections
        person_dets = [d for d in detections if d.class_name == "person"]

        # 2. Apply privacy blur to all persons
        blurred = ObjectDetector.apply_privacy_blur(
            frame=frame,
            person_detections=person_dets,
            kernel_size=blur_kernel_size,
        )

        # 3. Downscale to at most max_width (e.g. 320px wide) maintaining aspect ratio
        h, w = blurred.shape[:2]
        if w > max_width:
            scale = max_width / float(w)
            new_w = max_width
            new_h = max(1, int(h * scale))
            downscaled = cv2.resize(blurred, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            downscaled = blurred

        # 4. Encode as JPEG with ~50% quality
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
        success, encoded_img = cv2.imencode(".jpg", downscaled, encode_params)
        if not success:
            return None

        # 5. Write to local storage
        with open(target_file, "wb") as f:
            f.write(encoded_img.tobytes())

        byte_size = len(encoded_img)
        return str(target_file), byte_size

    @staticmethod
    def to_base64(file_path: str) -> Optional[str]:
        """
        Read thumbnail file and encode as base64 string for upload.
        """
        p = Path(file_path)
        if not p.exists():
            return None
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
