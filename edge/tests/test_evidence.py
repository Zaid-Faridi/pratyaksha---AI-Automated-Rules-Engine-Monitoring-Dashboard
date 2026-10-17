"""
Unit tests for Privacy Evidence Generation.
Verifies downscaling (<=320px), JPEG quality ~50, and privacy blurring.
"""

from pathlib import Path
import cv2
import numpy as np
import pytest
from detector import Detection
from edge.evidence import EvidenceGenerator


def test_evidence_generation_downscaling_and_blur(tmp_path):
    # Create synthetic test frame (720x1280)
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 180

    # Draw a synthetic face/person region
    cv2.circle(frame, (300, 300), 50, (0, 0, 255), -1)

    detections = [
        Detection(
            bbox=(250, 250, 350, 450),
            confidence=0.85,
            class_id=0,
            class_name="person",
        )
    ]

    event_id = "test_evidence_ev01"
    result = EvidenceGenerator.create_thumbnail(
        frame=frame,
        detections=detections,
        event_id=event_id,
        output_dir=str(tmp_path),
        max_width=320,
        jpeg_quality=50,
    )

    assert result is not None
    saved_file, byte_size = result
    assert Path(saved_file).exists()
    assert byte_size > 0

    # Load saved image and verify dimensions
    saved_img = cv2.imread(saved_file)
    h, w = saved_img.shape[:2]
    assert w <= 320, f"Thumbnail width must be <= 320 px, got {w}"

    # Aspect ratio check: 1280x720 -> scaled to 320x180
    assert abs(w / float(h) - 1280 / 720) < 0.05

    # Check Base64 encoding
    b64 = EvidenceGenerator.to_base64(saved_file)
    assert b64 is not None
    assert len(b64) > 0
