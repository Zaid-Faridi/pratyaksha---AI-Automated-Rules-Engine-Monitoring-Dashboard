"""
Detection Pipeline for Pratyaksha.
Orchestrates video ingestion, time-based frame sampling, zone-based spatial counting,
rolling median smoothing, privacy protection, and JSON Lines audit reporting.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import cv2

from detector import Detection, ObjectDetector
from zones import Zone, ZoneManager


class PratyakshaPipeline:
    """
    Main processing pipeline for video feeds or RTSP streams.
    """
    def __init__(
        self,
        config: Dict[str, Any],
        camera_id: Optional[str] = None,
        source_override: Optional[str] = None,
        sample_interval_override: Optional[float] = None,
        save_annotated_override: Optional[bool] = None,
        output_jsonl_override: Optional[str] = None,
    ) -> None:
        self.config = config
        pipeline_cfg = config.get("pipeline", {})

        # Interval settings
        self.sample_interval_sec = float(
            sample_interval_override
            if sample_interval_override is not None
            else pipeline_cfg.get("sample_interval_sec", 30)
        )
        self.smoothing_k = int(pipeline_cfg.get("smoothing_window_k", 5))

        # Privacy & storage settings
        self.save_annotated = (
            save_annotated_override
            if save_annotated_override is not None
            else bool(pipeline_cfg.get("save_annotated_frames", False))
        )
        self.annotated_dir = Path(pipeline_cfg.get("annotated_dir", "outputs/frames"))
        self.output_jsonl_path = Path(
            output_jsonl_override
            if output_jsonl_override is not None
            else pipeline_cfg.get("output_jsonl", "outputs/detections.jsonl")
        )
        self.blur_strength = int(pipeline_cfg.get("person_blur_strength", 35))

        # Class mappings (domain name -> list of COCO classes)
        self.class_mapping: Dict[str, List[str]] = config.get("class_mapping", {})

        # Camera selection
        cameras = config.get("cameras", {})
        if not cameras:
            raise ValueError("No cameras defined in configuration file.")

        self.camera_id = camera_id or list(cameras.keys())[0]
        if self.camera_id not in cameras:
            raise ValueError(f"Camera ID '{self.camera_id}' not found in configuration.")

        self.source = source_override or cameras[self.camera_id].get("source", "")
        if not self.source:
            raise ValueError(f"No video source specified for camera '{self.camera_id}'.")

        # Initialize Zone Manager
        self.zone_manager = ZoneManager.from_config(config, smoothing_k=self.smoothing_k)
        self.zones: Dict[str, Zone] = self.zone_manager.get_zones(self.camera_id)
        if not self.zones:
            print(f"[WARNING] No zones defined for camera '{self.camera_id}'.")

        # Initialize Object Detector
        model_name = pipeline_cfg.get("model_name", "yolov8n.pt")
        conf_thresh = float(pipeline_cfg.get("confidence_threshold", 0.25))
        device = pipeline_cfg.get("device", "")
        print(f"[INFO] Initializing YOLO detector ({model_name}) on device '{device or 'auto'}'...")
        self.detector = ObjectDetector(
            model_name=model_name,
            confidence_threshold=conf_thresh,
            device=device,
        )

        # Ensure output directories exist
        self.output_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        if self.save_annotated:
            self.annotated_dir.mkdir(parents=True, exist_ok=True)

    def _is_item_of_type(self, detected_class: str, target_item: str) -> bool:
        """
        Check if a detected YOLO class corresponds to the target infrastructure item.
        """
        valid_coco_classes = self.class_mapping.get(target_item, [target_item])
        return detected_class.lower() in [c.lower() for c in valid_coco_classes]

    def _process_sample(
        self,
        frame: Any,
        sample_index: int,
        timestamp_str: str,
    ) -> List[Dict[str, Any]]:
        """
        Process a single sampled frame through detection, zone filtering, and status audit.
        """
        # Step 1: Run YOLO object detection
        detections = self.detector.detect(frame)

        sample_records: List[Dict[str, Any]] = []

        # Step 2: Evaluate detections per zone
        print("\n" + "=" * 70)
        print(f"[SAMPLE #{sample_index:04d}] {timestamp_str} | Camera: {self.camera_id}")
        print("=" * 70)

        for zone_name, zone in self.zones.items():
            # A. Count persons in this zone (using bottom-center / foot-point ground position)
            zone_person_dets = [
                d for d in detections
                if d.class_name == "person" and zone.contains_point(d.foot_point)
            ]
            raw_person_count = len(zone_person_dets)
            raw_person_count, smoothed_person_count = zone.update_person_count(raw_person_count)

            # B. Count infrastructure items in this zone (using center point)
            detected_infra_counts: Dict[str, int] = {}
            for item in zone.expected_infrastructure.keys():
                matching_dets = [
                    d for d in detections
                    if d.class_name != "person"
                    and self._is_item_of_type(d.class_name, item)
                    and zone.contains_point(d.center_point)
                ]
                detected_infra_counts[item] = len(matching_dets)

            # C. Evaluate infrastructure status (MATCH, DEFICIT, SURPLUS)
            infra_evaluations = zone.evaluate_infrastructure(detected_infra_counts)

            # Build standardized output record
            record = {
                "timestamp": timestamp_str,
                "camera_id": self.camera_id,
                "zone": zone_name,
                "person_count": {
                    "raw": raw_person_count,
                    "smoothed": smoothed_person_count,
                },
                "infrastructure": infra_evaluations,
            }
            sample_records.append(record)

            # Print readable terminal summary
            print(f"Zone: '{zone_name}'")
            print(f"  • Attendance (Persons) : Raw = {raw_person_count:2d} | Smoothed (Rolling Median K={self.smoothing_k}) = {smoothed_person_count:2d}")
            print("  • Sanctioned Infrastructure Audit:")
            if not infra_evaluations:
                print("      (No expected infrastructure configured)")
            for item_eval in infra_evaluations:
                status = item_eval["status"]
                exp = item_eval["expected"]
                det = item_eval["detected"]
                diff = det - exp
                diff_str = f"+{diff}" if diff > 0 else str(diff)
                status_symbol = "[OK]" if status == "MATCH" else ("[ALERT DEFICIT]" if status == "DEFICIT" else "[SURPLUS]")
                print(f"      - {item_eval['item']:<12}: Expected = {exp:2d} | Detected = {det:2d} | Diff = {diff_str:>3s} | Status: {status_symbol}")
            print("-" * 70)

        # Step 3: Append results to JSON Lines audit log
        with open(self.output_jsonl_path, "a", encoding="utf-8") as f:
            for rec in sample_records:
                f.write(json.dumps(rec) + "\n")

        # Step 4: Optional diagnostic visualization (with strictly blurred persons)
        if self.save_annotated:
            annotated_frame = ObjectDetector.annotate_frame(
                frame=frame,
                detections=detections,
                zones=self.zones,
                class_mapping=self.class_mapping,
                blur_persons=True,
                blur_kernel_size=self.blur_strength,
            )
            out_file = self.annotated_dir / f"{self.camera_id}_sample_{sample_index:04d}.jpg"
            cv2.imwrite(str(out_file), annotated_frame)
            print(f"[PRIVACY] Anonymized frame saved (persons blurred): {out_file}")

        return sample_records

    def run(self, max_samples: Optional[int] = None) -> None:
        """
        Execute the detection pipeline on the configured video source or RTSP stream.
        """
        print(f"[INFO] Opening video stream/file: {self.source}")
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video stream or file at '{self.source}'")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps > 120:
            fps = 25.0  # Sensible fallback for streams without explicit FPS metadata

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        is_live_stream = total_frames <= 0 or str(self.source).startswith("rtsp://")

        # Calculate frame jump interval for stored video files
        frame_interval_step = max(1, int(round(fps * self.sample_interval_sec)))

        print(f"[INFO] Source details: FPS={fps:.1f}, Total Frames={total_frames if not is_live_stream else 'LIVE STREAM'}")
        print(f"[INFO] Sampling configured at 1 frame every {self.sample_interval_sec:.1f}s (step={frame_interval_step} frames)")
        print(f"[INFO] Privacy Mode: {'Saving Anonymized (Blurred) Frames' if self.save_annotated else 'Strict (NO frames saved)'}")
        print(f"[INFO] Output JSON Lines: {self.output_jsonl_path}")

        sample_count = 0
        current_frame_pos = 0
        last_realtime_sample = 0.0

        try:
            while True:
                if max_samples is not None and sample_count >= max_samples:
                    print(f"\n[INFO] Reached requested sample limit ({max_samples}). Stopping pipeline.")
                    break

                if is_live_stream:
                    # Live RTSP stream: continuously read frames and sample by wall-clock time
                    ret, frame = cap.read()
                    if not ret:
                        print("[INFO] Live stream ended or temporarily unavailable.")
                        break

                    now = time.time()
                    if now - last_realtime_sample < self.sample_interval_sec:
                        continue

                    last_realtime_sample = now
                    timestamp_str = datetime.now(timezone.utc).isoformat()
                    sample_count += 1
                    self._process_sample(frame, sample_count, timestamp_str)

                else:
                    # Video file: seek directly to next sample timestamp for fast processing
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_pos)
                    ret, frame = cap.read()
                    if not ret:
                        print("\n[INFO] End of video file reached.")
                        break

                    # Video-based timestamp
                    timestamp_sec = current_frame_pos / fps
                    timestamp_str = datetime.fromtimestamp(1700000000 + timestamp_sec, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                    sample_count += 1
                    self._process_sample(frame, sample_count, timestamp_str)

                    current_frame_pos += frame_interval_step
                    if current_frame_pos >= total_frames:
                        print("\n[INFO] Reached end of video frames.")
                        break

        except KeyboardInterrupt:
            print("\n[INFO] Pipeline interrupted by user.")
        finally:
            cap.release()
            print(f"\n[COMPLETE] Pipeline finished. Total samples processed: {sample_count}")
            print(f"[COMPLETE] Audit records appended to: {self.output_jsonl_path}")
