"""
Pratyaksha Edge Agent Service.
Long-running resilient edge process for monitoring government skilling centres on low-end hardware.
Features:
- Camera reconnect with exponential backoff
- Offline-first SQLite outbox queue with UUID idempotency
- Dynamic adaptive profiles (normal / low / ultra_low) based on CPU & queue backup
- Local schedule caching to skip sampling outside active batch hours
- Strict privacy: zero facial/identity data stored; all evidence thumbnails are pre-blurred
- Log rotation and zero-raw-video retention
"""

from datetime import datetime, timezone
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import sys
import time

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from typing import Any, Dict, List, Optional
import cv2
import yaml

from edge.adaptive import AdaptiveController
from edge.config import EdgeConfig
from edge.detector_runtime import EdgeDetectorRuntime
from edge.evidence import EvidenceGenerator
from edge.outbox import OutboxQueue
from edge.schedule_cache import ScheduleCache
from edge.sync_worker import SyncWorker
from zones import Zone, ZoneManager


def setup_logger(log_file: str) -> logging.Logger:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("pratyaksha")
    logger.setLevel(logging.INFO)

    # Format
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (5 MB per file, max 3 files)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


class EdgeAgent:
    """
    Main Pratyaksha edge monitoring service.
    """
    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config = EdgeConfig.load(config_path)
        self.logger = setup_logger(self.config.log_file)

        self.logger.info("=" * 70)
        self.logger.info("Initializing Pratyaksha Edge Monitoring Agent (Phase 4)")
        self.logger.info(f"Centre ID: {self.config.centre_id} | Camera ID: {self.config.camera_id}")
        self.logger.info(f"Target Backend: {self.config.backend_url}")
        self.logger.info(f"Initial Profile: {self.config.profile_name} ({self.config.profile.description})")
        self.logger.info("=" * 70)

        # 1. Initialize SQLite Outbox
        self.outbox = OutboxQueue(db_path=self.config.db_path)

        # 2. Adaptive Controller
        self.adaptive = AdaptiveController(config=self.config, outbox=self.outbox)

        # 3. Local Schedule & Inventory Cache
        self.schedule_cache = ScheduleCache(config=self.config)

        # 4. Detector Runtime
        self.detector = EdgeDetectorRuntime(
            model_path=self.config.model_path,
            onnx_path=self.config.onnx_path,
            prefer_onnx=self.config.prefer_onnx,
        )

        # 5. Zone Manager (Reused from Phase 1)
        base_cfg_path = "config.yaml"
        base_cfg = {}
        if os.path.exists(base_cfg_path):
            with open(base_cfg_path, "r", encoding="utf-8") as f:
                base_cfg = yaml.safe_load(f) or {}

        self.zone_manager = ZoneManager.from_config(base_cfg, smoothing_k=5)
        self.zones: Dict[str, Zone] = self.zone_manager.get_zones(self.config.camera_id)
        self.class_mapping: Dict[str, List[str]] = base_cfg.get("class_mapping", {})

        # 6. Background Sync Worker
        self.sync_worker = SyncWorker(
            config=self.config,
            outbox=self.outbox,
            adaptive=self.adaptive,
        )

        self.running = False

    def _is_item_of_type(self, detected_class: str, target_item: str) -> bool:
        valid_coco_classes = self.class_mapping.get(target_item, [target_item])
        return detected_class.lower() in [c.lower() for c in valid_coco_classes]

    def _process_frame(self, frame: Any, sample_idx: int) -> None:
        """
        Execute detection, spatial zone counting, local alert detection,
        privacy evidence thumbnail generation, and SQLite outbox queuing.
        """
        profile = self.adaptive.current_profile
        now_dt = datetime.now(timezone.utc)
        timestamp_str = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Run detection at profile-adapted resolution
        detections = self.detector.detect(frame, imgsz=profile.input_resolution)

        # 2. Process zones
        for zone_name, zone in self.zones.items():
            # Person detection (ground foot-point anchor)
            zone_persons = [
                d for d in detections
                if d.class_name == "person" and zone.contains_point(d.foot_point)
            ]
            raw_count = len(zone_persons)
            raw_count, smoothed_count = zone.update_person_count(raw_count)

            # Infrastructure detection (center-point anchor)
            # Use cached inventory if available, otherwise zone expected
            expected_inv = self.schedule_cache.get_expected_inventory(zone_name) or zone.expected_infrastructure
            detected_counts: Dict[str, int] = {}
            has_deficit = False

            for item in expected_inv.keys():
                matching = [
                    d for d in detections
                    if d.class_name != "person"
                    and self._is_item_of_type(d.class_name, item)
                    and zone.contains_point(d.center_point)
                ]
                count = len(matching)
                detected_counts[item] = count
                if count < expected_inv[item]:
                    has_deficit = True

            infra_evals = zone.evaluate_infrastructure(detected_counts)

            # Build standardized event record
            event_record = {
                "timestamp": timestamp_str,
                "camera_id": self.config.camera_id,
                "zone": zone_name,
                "person_count": {
                    "raw": raw_count,
                    "smoothed": smoothed_count,
                },
                "infrastructure": infra_evals,
            }

            # 3. Check for alert-worthy conditions for privacy-preserving evidence
            evidence_file = None
            if self.adaptive.should_generate_evidence(is_deficit=has_deficit):
                event_id_temp = f"{self.config.camera_id}_{sample_idx:05d}_{int(time.time())}"
                thumb_result = EvidenceGenerator.create_thumbnail(
                    frame=frame,
                    detections=detections,
                    event_id=event_id_temp,
                    output_dir=self.config.evidence_dir,
                    max_width=320,
                    jpeg_quality=50,
                )
                if thumb_result:
                    evidence_file = thumb_result[0]

            # 4. Atomically persist to SQLite Outbox
            event_id = self.outbox.enqueue_event(event_record, evidence_path=evidence_file)
            self.sync_worker.last_sample_time_iso = timestamp_str

            self.logger.info(
                f"[SAMPLE #{sample_idx}] Zone '{zone_name}': {raw_count} persons (smoothed: {smoothed_count}) | "
                f"Infra items: {len(infra_evals)} | Event UUID: {event_id[:8]}... | "
                f"Evidence: {'Saved (Blurred)' if evidence_file else 'None'}"
            )

    def run(self, max_samples: Optional[int] = None) -> None:
        """
        Main resilient edge processing loop.
        Handles camera disconnects with automatic reconnect and exponential backoff.
        """
        self.running = True
        self.sync_worker.start()

        # Initial schedule refresh
        self.schedule_cache.refresh_from_backend()

        sample_idx = 0
        reconnect_delay = self.config.reconnect_initial_delay_sec
        cap: Optional[cv2.VideoCapture] = None

        self.logger.info(f"[EDGE SERVICE] Starting monitoring on source: {self.config.source}")

        try:
            while self.running:
                if max_samples is not None and sample_idx >= max_samples:
                    self.logger.info(f"Reached sample limit ({max_samples}). Stopping.")
                    break

                # 1. Ensure camera connection is active
                if cap is None or not cap.isOpened():
                    self.logger.info(f"[CAMERA CONNECT] Opening stream '{self.config.source}'...")
                    cap = cv2.VideoCapture(self.config.source)
                    if not cap.isOpened():
                        self.logger.warning(
                            f"[CAMERA OFFLINE] Unable to connect. Retrying in {reconnect_delay:.1f}s..."
                        )
                        time.sleep(reconnect_delay)
                        reconnect_delay = min(self.config.reconnect_max_delay_sec, reconnect_delay * self.config.reconnect_backoff_factor)
                        continue
                    else:
                        self.logger.info("[CAMERA ONLINE] Video stream connected successfully.")
                        reconnect_delay = self.config.reconnect_initial_delay_sec

                # 2. Check schedule pre-checks (skip sampling outside batch hours)
                is_active, active_batch = self.schedule_cache.is_batch_active()
                if not is_active:
                    self.logger.debug("[SCHEDULE IDLE] Outside active training batch hours. Sleeping to conserve compute.")
                    time.sleep(10.0)
                    continue

                # 3. Read frame
                ret, frame = cap.read()
                if not ret:
                    self.logger.warning("[CAMERA READ ERROR] Frame drop or stream disconnected.")
                    cap.release()
                    cap = None
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(self.config.reconnect_max_delay_sec, reconnect_delay * self.config.reconnect_backoff_factor)
                    continue

                # 4. Evaluate adaptive resource state
                profile, adapt_msg = self.adaptive.evaluate_adaptive_state()
                if adapt_msg != "Stable":
                    self.logger.info(f"[ADAPTIVE] {adapt_msg}")

                # 5. Process frame
                sample_idx += 1
                self._process_frame(frame, sample_idx)

                # 6. Sleep for adapted sample interval
                time.sleep(profile.sample_interval_sec)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received.")
        except Exception as exc:
            self.logger.error(f"Unexpected error in edge agent: {exc}", exc_info=True)
        finally:
            self.stop()
            if cap is not None:
                cap.release()
            self.logger.info("[EDGE SERVICE] Agent successfully stopped.")

    def stop(self) -> None:
        self.running = False
        self.sync_worker.stop()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pratyaksha Low-Bandwidth Edge Agent")
    parser.add_argument("--config", "-c", type=str, default=None, help="Path to edge_config.yaml")
    parser.add_argument("--profile", "-p", type=str, default=None, choices=["ultra_low", "low", "normal"], help="Override profile")
    parser.add_argument("--samples", "-s", type=int, default=None, help="Process N samples then exit")
    parser.add_argument("--source", type=str, default=None, help="Video source or RTSP stream")
    args = parser.parse_args()

    agent = EdgeAgent(config_path=args.config)
    if args.profile:
        agent.config.profile_name = args.profile
    if args.source:
        agent.config.source = args.source

    def handle_signal(sig, frame):
        agent.logger.info(f"Signal {sig} received. Gracefully shutting down...")
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    agent.run(max_samples=args.samples)


if __name__ == "__main__":
    main()
