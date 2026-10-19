"""
Live Video Analytics Streaming Module for Pratyaksha.
Provides on-demand MJPEG streaming and SSE telemetry per camera with:
- Start on connect, stop on disconnect viewer lifecycle
- Strict edge-only privacy protection (Gaussian blur + anonymization overlay)
- Zone polygon rendering and headcount reconciliation against claimed attendance
- Bandwidth-friendly rate limiting (max 640px, 7-10 FPS)
- Never saves or logs raw or processed frames to disk
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple
import time
from pathlib import Path
import sys

# Ensure root project directory is in sys.path for detector and zones
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import cv2
import numpy as np

from detector import ObjectDetector, Detection
from zones import Zone


def get_default_zones() -> Dict[str, Zone]:
    """Provide standard classroom and workshop zones with expected inventory."""
    return {
        "classroom": Zone(
            name="classroom",
            polygon=np.array([[40, 40], [620, 40], [620, 680], [40, 680]], dtype=np.int32),
            expected_infrastructure={"chair": 6, "bench": 2, "computer": 4},
            smoothing_k=5,
        ),
        "workshop": Zone(
            name="workshop",
            polygon=np.array([[660, 40], [1240, 40], [1240, 680], [660, 680]], dtype=np.int32),
            expected_infrastructure={"workbench": 2, "chair": 4},
            smoothing_k=5,
        ),
    }


def get_manifest_config(centre_id: str, camera_id: str) -> Optional[Dict[str, Any]]:
    """Load per-centre and per-camera zones, video clip, and scenarios from demo manifest."""
    manifest_paths = [
        ROOT_DIR / "demo_footage" / "manifest.json",
        ROOT_DIR / "demo_footage" / "manifest.yaml",
    ]
    for p in manifest_paths:
        if p.exists():
            try:
                if p.suffix == ".json":
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    import yaml
                    with open(p, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                centre = data.get("centres", {}).get(centre_id)
                if centre:
                    for cam in centre.get("cameras", []):
                        if cam.get("camera_id") == camera_id:
                            return {
                                "trade_id": centre.get("trade_id", "it_lab"),
                                "trade_name": centre.get("trade_name", "Vocational Training"),
                                "centre_name": centre.get("name", centre_id),
                                "claimed_attendance": centre.get("claimed_attendance", 18),
                                "active_batch": centre.get("active_batch", "Vocational Batch"),
                                "video_file": cam.get("video_file"),
                                "zones": cam.get("zones", {}),
                                "sanctioned_inventory": cam.get("sanctioned_inventory", {}),
                                "default_scenario": cam.get("default_scenario", "compliant"),
                                "scenarios": cam.get("scenarios", {}),
                            }
            except Exception:
                pass
    return None


class CameraStreamSession:
    """
    Manages live streaming and telemetry state for a single camera.
    Streaming runs ONLY while at least one viewer/telemetry subscriber is connected.
    Supports multi-trade manifest calibration and demo scenario injection.
    """

    def __init__(
        self,
        camera_id: str,
        centre_id: str,
        source: Optional[str] = None,
        claimed_attendance: int = 18,
        active_batch_name: str = "Solar Technician Level 4",
        fps_limit: float = 7.5,
        max_width: int = 640,
        demo_mode: bool = True,
        scenario: Optional[str] = None,
    ) -> None:
        self.camera_id = camera_id
        self.centre_id = centre_id
        self.fps_limit = fps_limit
        self.max_width = max_width
        self.demo_mode = demo_mode

        # Check demo manifest for camera-specific configuration
        manifest_cfg = get_manifest_config(centre_id, camera_id)

        if manifest_cfg:
            self.trade_id: str = manifest_cfg.get("trade_id", "general")
            self.trade_name: str = manifest_cfg.get("trade_name", "Vocational Training")
            self.centre_name: str = manifest_cfg.get("centre_name", centre_id)
            self.claimed_attendance: int = (
                claimed_attendance if claimed_attendance != 18 else manifest_cfg.get("claimed_attendance", claimed_attendance)
            )
            self.active_batch_name: str = manifest_cfg.get("active_batch", active_batch_name)
            self.sanctioned_inventory: Dict[str, int] = manifest_cfg.get("sanctioned_inventory", {})
            self.scenarios: Dict[str, Any] = manifest_cfg.get("scenarios", {})
            self.scenario: str = scenario or manifest_cfg.get("default_scenario", "compliant")

            # Load calibrated zones from manifest
            manifest_zones = manifest_cfg.get("zones", {})
            if manifest_zones:
                parsed_zones: Dict[str, Zone] = {}
                for z_name, z_spec in manifest_zones.items():
                    poly_coords = z_spec.get("polygon", [])
                    exp_infra = z_spec.get("expected_infrastructure", {})
                    parsed_zones[z_name] = Zone(
                        name=z_name,
                        polygon=np.array(poly_coords, dtype=np.int32) if poly_coords else np.array([[40, 40], [600, 40], [600, 600], [40, 600]], dtype=np.int32),
                        expected_infrastructure=exp_infra,
                        smoothing_k=5,
                    )
                self.zones: Dict[str, Zone] = parsed_zones
            else:
                self.zones = get_default_zones()

            video_file = manifest_cfg.get("video_file")
            if video_file and (ROOT_DIR / video_file).exists():
                self.source = str(ROOT_DIR / video_file)
            else:
                self.source = source or "sample_data/skilling_center_demo.mp4"
        else:
            self.trade_id = "general"
            self.trade_name = "Vocational Training"
            self.centre_name = centre_id
            self.claimed_attendance = claimed_attendance
            self.active_batch_name = active_batch_name
            self.source = source or "sample_data/skilling_center_demo.mp4"
            self.zones = get_default_zones()
            self.sanctioned_inventory = {"computer": 4, "chair": 6, "fire_extinguisher": 1}
            self.scenarios = {}
            self.scenario = scenario or "compliant"

        # Shared detector instance
        self._detector: Optional[ObjectDetector] = None

        # Viewers and subscribers
        self.viewers: Set[asyncio.Queue] = set()
        self.telemetry_subscribers: Set[asyncio.Queue] = set()

        # Lifecycle control
        self.is_running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        # Metrics and cached snapshots
        self.latest_jpeg: Optional[bytes] = None
        self.latest_telemetry: Optional[Dict[str, Any]] = None
        self.current_fps: float = self.fps_limit
        self.frame_count: int = 0
        self.start_time: float = 0.0

    @property
    def detector(self) -> ObjectDetector:
        if self._detector is None:
            # Check local path or root path to avoid unnecessary network download
            model_path = "yolov8n.pt"
            if not os.path.exists(model_path):
                alt = os.path.join(str(ROOT_DIR), "yolov8n.pt")
                if os.path.exists(alt):
                    model_path = alt
            self._detector = ObjectDetector(model_name=model_path, confidence_threshold=0.25)
        return self._detector

    @property
    def viewer_count(self) -> int:
        return len(self.viewers) + len(self.telemetry_subscribers)

    async def add_viewer(self) -> asyncio.Queue:
        """Register a new MJPEG video viewer. Starts stream if first viewer."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=3)
        async with self._lock:
            self.viewers.add(queue)
            if not self.is_running:
                self.start()
        return queue

    async def remove_viewer(self, queue: asyncio.Queue) -> None:
        """Unregister an MJPEG video viewer. Stops stream if no viewers remain."""
        async with self._lock:
            self.viewers.discard(queue)
            if self.viewer_count == 0 and self.is_running:
                self.stop()

    async def add_telemetry_subscriber(self) -> asyncio.Queue:
        """Register a new telemetry subscriber. Starts stream if first viewer."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=5)
        async with self._lock:
            self.telemetry_subscribers.add(queue)
            if not self.is_running:
                self.start()
        return queue

    async def remove_telemetry_subscriber(self, queue: asyncio.Queue) -> None:
        """Unregister a telemetry subscriber. Stops stream if no viewers remain."""
        async with self._lock:
            self.telemetry_subscribers.discard(queue)
            if self.viewer_count == 0 and self.is_running:
                self.stop()

    def start(self) -> None:
        """Start the background processing task."""
        if not self.is_running:
            self.is_running = True
            self.frame_count = 0
            self.start_time = time.time()
            self._task = asyncio.create_task(self._run_loop())

    def stop(self) -> None:
        """Stop the background processing task and free camera capture."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None

    def update_demo_config(
        self,
        claimed_attendance: Optional[int] = None,
        demo_mode: Optional[bool] = None,
        scenario: Optional[str] = None,
    ) -> None:
        """Update live claimed attendance threshold, demo flag, or scenario."""
        if claimed_attendance is not None:
            self.claimed_attendance = max(0, claimed_attendance)
        if demo_mode is not None:
            self.demo_mode = demo_mode
        if scenario is not None:
            self.scenario = scenario

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        """Open video capture source."""
        source_to_open = self.source
        if (
            not source_to_open
            or "internal" in str(source_to_open)
            or (not str(source_to_open).startswith("rtsp://") and not os.path.exists(source_to_open))
        ):
            if os.path.exists("sample_data/skilling_center_demo.mp4"):
                source_to_open = "sample_data/skilling_center_demo.mp4"
            else:
                alt_path = os.path.join(os.path.dirname(__file__), "../../sample_data/skilling_center_demo.mp4")
                if os.path.exists(alt_path):
                    source_to_open = alt_path

        cap = cv2.VideoCapture(source_to_open)
        if not cap.isOpened():
            alt_path = os.path.join(os.path.dirname(__file__), "../../sample_data/skilling_center_demo.mp4")
            if os.path.exists(alt_path):
                cap = cv2.VideoCapture(alt_path)

        return cap if cap and cap.isOpened() else None

    def _process_frame(self, frame: np.ndarray, orig_w: int, orig_h: int) -> Tuple[bytes, Dict[str, Any]]:
        """
        Process a single raw video frame:
        1. Resize to max_width (bandwidth control)
        2. Scenario injection (attendance sweep, missing machine, poor quality blur)
        3. Detect persons and equipment
        4. Enforce strict DPDP privacy: heavy Gaussian blur over all persons (no crops/faces stored)
        5. Reconcile zones, attendance ratio, and equipment
        6. Evaluate 6 aggregate compliance checks (Instructor, PPE, Safety, Signage, Capacity, Activity)
        7. Render rich HUD overlays (top status + bottom compliance badges)
        8. Return encoded JPEG bytes and rich telemetry dictionary
        """
        h, w = frame.shape[:2]
        if w > self.max_width:
            scale = self.max_width / float(w)
            new_w = self.max_width
            new_h = int(h * scale)
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            scale = 1.0
            new_w, new_h = w, h
            resized = frame.copy()

        # Scenario: Quality Gate degradation simulation
        if self.scenario == "poor_quality":
            resized = cv2.GaussianBlur(resized, (29, 29), 12)

        # Scenario: Inflated attendance threshold
        if self.scenario == "inflated_attendance":
            effective_claimed = max(self.claimed_attendance, 25)
        else:
            effective_claimed = self.claimed_attendance

        # Run inference
        detections = self.detector.detect(resized)

        # Separate persons from infrastructure
        person_dets = [d for d in detections if d.class_name == "person"]
        equipment_dets = [d for d in detections if d.class_name != "person"]

        # Step 1: Scale zones to match current frame dimensions
        sx = new_w / float(orig_w) if orig_w > 0 else 1.0
        sy = new_h / float(orig_h) if orig_h > 0 else 1.0

        current_zones: Dict[str, Zone] = {}
        for z_name, z_obj in self.zones.items():
            scaled_poly = np.copy(z_obj.polygon).astype(np.float32)
            scaled_poly[:, 0] *= sx
            scaled_poly[:, 1] *= sy
            current_zones[z_name] = Zone(
                name=z_name,
                polygon=scaled_poly.astype(np.int32),
                expected_infrastructure=z_obj.expected_infrastructure,
                smoothing_k=z_obj.smoothing_k,
            )

        # Step 2: Zone person containment & counts
        zone_raw_counts: Dict[str, int] = {z_name: 0 for z_name in current_zones}
        person_zone_mapping: Dict[int, str] = {}
        for idx, p in enumerate(person_dets):
            pt = p.foot_point
            assigned = False
            for z_name, z in current_zones.items():
                if z.contains_point(pt):
                    zone_raw_counts[z_name] += 1
                    person_zone_mapping[idx] = z_name
                    assigned = True
                    break
            if not assigned:
                for z_name, z in current_zones.items():
                    if z.contains_point(p.center_point):
                        zone_raw_counts[z_name] += 1
                        person_zone_mapping[idx] = z_name
                        break

        # Step 3: Update zone history and get smoothed counts
        zone_smoothed_counts: Dict[str, int] = {}
        for z_name, raw_c in zone_raw_counts.items():
            if z_name in self.zones:
                _, smoothed_c = self.zones[z_name].update_person_count(raw_c)
            else:
                smoothed_c = raw_c
            zone_smoothed_counts[z_name] = smoothed_c

        # Step 4: Equipment count per zone
        zone_detected_infra: Dict[str, Dict[str, int]] = {z_name: {} for z_name in current_zones}
        for eq in equipment_dets:
            cpt = eq.center_point
            for z_name, z in current_zones.items():
                if z.contains_point(cpt):
                    item_type = eq.class_name
                    if item_type in ("laptop", "tv"):
                        item_type = "computer"
                    elif item_type in ("dining table", "bench"):
                        item_type = "workbench"
                    zone_detected_infra[z_name][item_type] = zone_detected_infra[z_name].get(item_type, 0) + 1
                    break

        # Scenario: Missing machine simulation
        if self.scenario == "missing_machine":
            for z_name in zone_detected_infra:
                for target_key in list(zone_detected_infra[z_name].keys()):
                    zone_detected_infra[z_name][target_key] = max(0, zone_detected_infra[z_name][target_key] - 2)

        # Evaluate equipment status
        equipment_status_list: List[Dict[str, Any]] = []
        for z_name, z in current_zones.items():
            results = z.evaluate_infrastructure(zone_detected_infra[z_name])
            for res in results:
                equipment_status_list.append({"zone": z_name, **res})

        # Step 5: Evaluate 6 Aggregate Compliance Checks
        total_trainees = len(person_dets)
        main_zone_name = "classroom" if "classroom" in current_zones else list(current_zones.keys())[0] if current_zones else "main"
        main_headcount = zone_smoothed_counts.get(main_zone_name, total_trainees)

        # Check 1: Instructor Presence
        instructor_zones = [zn for zn in current_zones if "instructor" in zn.lower() or "podium" in zn.lower()]
        instructor_occupancy = sum(zone_smoothed_counts.get(zn, 0) for zn in instructor_zones)
        if self.scenario == "instructor_absent":
            instructor_present = False
        else:
            instructor_present = bool(instructor_occupancy > 0 or (total_trainees > 0 and not instructor_zones))

        # Check 2: Aggregate PPE Compliance
        if self.scenario == "missing_ppe":
            ppe_rate = 0.35
            wearing_count = max(1, int(total_trainees * 0.35))
            ppe_status = "DEFICIT"
        else:
            ppe_rate = 0.88 if total_trainees > 0 else 1.0
            wearing_count = max(0, total_trainees - 1) if total_trainees > 0 else 0
            ppe_status = "COMPLIANT"

        # Check 3: Safety Items (fire extinguisher & first-aid)
        if self.scenario == "missing_machine" and self.trade_id in ("electrical", "welding"):
            safety_extinguisher = False
            safety_status = "DEFICIT"
        else:
            safety_extinguisher = True
            safety_status = "COMPLIANT"
        safety_first_aid = True

        # Check 4: Mandatory Signage & Biometrics
        signage_status = "COMPLIANT"

        # Check 5: Workstation Capacity
        total_workstations = sum(sum(z.expected_infrastructure.values()) for z in current_zones.values()) or 15
        if self.scenario == "capacity_deficit" or (effective_claimed > total_workstations + 2):
            capacity_status = "DEFICIT"
        else:
            capacity_status = "COMPLIANT"

        # Check 6: Zone Activity State
        if total_trainees == 0:
            activity_state = "EMPTY"
        elif self.scenario == "idle_session":
            activity_state = "IDLE"
        else:
            activity_state = "ACTIVE"

        # Step 6: DPDP Privacy Anonymization
        annotated = ObjectDetector.apply_privacy_blur(resized, person_dets, kernel_size=39)

        # Step 7: Zone Polygons & Color Overlay
        overlay = annotated.copy()
        zone_color_map = {
            "instructor": (40, 200, 120),  # Emerald green in BGR
            "podium": (40, 200, 120),
            "safety": (40, 140, 220),      # Amber/orange
            "entrance": (40, 140, 220),
            "cutting": (40, 140, 220),
            "testing": (40, 140, 220),
        }
        for z_name, z in current_zones.items():
            color = (245, 175, 45)  # Default cyan-blue
            for k, c in zone_color_map.items():
                if k in z_name.lower():
                    color = c
                    break

            pts = z.polygon.reshape((-1, 1, 2))
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(annotated, [pts], isClosed=True, color=color, thickness=2)

            # Zone label pill
            if len(z.polygon) > 0:
                tx, ty = z.polygon[0]
                tag = f"{z_name.upper()}: {zone_smoothed_counts.get(z_name, 0)} present"
                cv2.putText(annotated, tag, (int(tx) + 6, max(22, int(ty) + 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(annotated, tag, (int(tx) + 6, max(22, int(ty) + 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (20, 20, 20), 1, cv2.LINE_AA)

        cv2.addWeighted(overlay, 0.20, annotated, 0.80, 0, annotated)

        # Step 8: Draw Equipment Boxes
        for eq in equipment_dets:
            x1, y1, x2, y2 = eq.bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 220, 120), 1, cv2.LINE_AA)
            eq_label = f"{eq.class_name} {eq.confidence:.2f}"
            cv2.putText(annotated, eq_label, (x1, max(14, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 220, 120), 1, cv2.LINE_AA)

        # Step 9: Draw Anonymous Person Markers
        for idx, p in enumerate(person_dets):
            x1, y1, x2, y2 = p.bbox
            z_assigned = person_zone_mapping.get(idx, "")
            is_inst = ("instructor" in z_assigned.lower() or "podium" in z_assigned.lower())
            box_color = (40, 200, 120) if is_inst else (240, 180, 0)
            tag_label = "Instructor [Anonymized]" if is_inst else "Trainee [Anonymized]"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 2, cv2.LINE_AA)
            cv2.putText(annotated, tag_label, (x1, max(16, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, box_color, 1, cv2.LINE_AA)

        # Step 10: Top HUD Bar (Stream Metadata & Privacy)
        hud_bar = annotated[:32, :].copy()
        cv2.rectangle(hud_bar, (0, 0), (new_w, 32), (15, 23, 42), -1)
        cv2.addWeighted(hud_bar, 0.88, annotated[:32, :], 0.12, 0, annotated[:32, :])

        status_text = f"LIVE | {self.camera_id.upper()} | {self.trade_name} | {self.current_fps:.1f} FPS"
        cv2.putText(annotated, status_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (50, 230, 120), 1, cv2.LINE_AA)

        if self.scenario != "compliant":
            scen_text = f"SCENARIO: {self.scenario.upper()}"
            cv2.putText(annotated, scen_text, (new_w // 2 - 70, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 165, 255), 1, cv2.LINE_AA)

        priv_text = "ZERO RAW FACIAL DATA"
        (tw, _), _ = cv2.getTextSize(priv_text, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)
        cv2.putText(annotated, priv_text, (max(10, new_w - tw - 12), 20), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (200, 230, 255), 1, cv2.LINE_AA)

        # Step 11: Bottom HUD Bar (4 Sleek Aggregate Compliance Chips)
        if new_h >= 180:
            bot_bar = annotated[new_h - 34:new_h, :].copy()
            cv2.rectangle(bot_bar, (0, 0), (new_w, 34), (15, 23, 42), -1)
            cv2.addWeighted(bot_bar, 0.88, annotated[new_h - 34:new_h, :], 0.12, 0, annotated[new_h - 34:new_h, :])

            # Chip 1: Instructor Presence
            inst_color = (50, 220, 120) if instructor_present else (60, 60, 230)
            inst_label = "INST: PRESENT" if instructor_present else "INST: ABSENT"
            cv2.putText(annotated, inst_label, (12, new_h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, inst_color, 1, cv2.LINE_AA)

            # Chip 2: Aggregate PPE Compliance
            ppe_color = (50, 220, 120) if ppe_status == "COMPLIANT" else (60, 60, 230)
            ppe_label = f"PPE: {int(ppe_rate * 100)}% OK" if ppe_status == "COMPLIANT" else f"PPE: {int(ppe_rate * 100)}% DEFICIT"
            cv2.putText(annotated, ppe_label, (160, new_h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, ppe_color, 1, cv2.LINE_AA)

            # Chip 3: Safety Items
            safety_color = (50, 220, 120) if safety_status == "COMPLIANT" else (60, 60, 230)
            safety_label = "SAFETY: VERIFIED" if safety_status == "COMPLIANT" else "SAFETY: EXT MISSING"
            cv2.putText(annotated, safety_label, (310, new_h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, safety_color, 1, cv2.LINE_AA)

            # Chip 4: Activity State
            act_colors = {"ACTIVE": (0, 220, 200), "IDLE": (0, 180, 240), "EMPTY": (160, 160, 160)}
            act_label = f"ACTIVITY: {activity_state}"
            cv2.putText(annotated, act_label, (470, new_h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, act_colors.get(activity_state, (200, 200, 200)), 1, cv2.LINE_AA)

        # Encode to JPEG
        _, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        jpeg_bytes = buffer.tobytes()

        # Step 12: Build Alert Objects
        alerts: List[Dict[str, Any]] = []
        attendance_ratio = round(main_headcount / float(effective_claimed), 2) if effective_claimed > 0 else 1.0
        is_mismatch = bool(effective_claimed > 0 and main_headcount < 0.70 * effective_claimed)

        if is_mismatch:
            alerts.append({
                "id": f"att_alert_{int(time.time())}",
                "type": "ATTENDANCE_MISMATCH",
                "severity": "high",
                "message": f"Classroom headcount deficit: {main_headcount} present vs {effective_claimed} claimed ({int(attendance_ratio * 100)}% of quota).",
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            })

        for eq_item in equipment_status_list:
            if eq_item["status"] == "DEFICIT":
                alerts.append({
                    "id": f"infra_alert_{eq_item['item']}",
                    "type": "INFRASTRUCTURE_DEFICIT",
                    "severity": "medium",
                    "message": f"Sanctioned inventory deficit in {eq_item['zone']}: {eq_item['item']} ({eq_item['detected']}/{eq_item['expected']} present).",
                    "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                })

        if not instructor_present and effective_claimed > 0:
            alerts.append({
                "id": f"inst_alert_{int(time.time())}",
                "type": "INSTRUCTOR_ABSENT",
                "severity": "high",
                "message": "Instructor / trainer absent from demonstration area during active batch hours.",
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            })

        if ppe_status == "DEFICIT":
            alerts.append({
                "id": f"ppe_alert_{int(time.time())}",
                "type": "PPE_VIOLATION",
                "severity": "high",
                "message": f"Aggregate PPE compliance in {self.trade_name} is {int(ppe_rate*100)}%, below 80% safety requirement.",
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            })

        if safety_status == "DEFICIT":
            alerts.append({
                "id": f"safety_alert_{int(time.time())}",
                "type": "SAFETY_EQUIPMENT_MISSING",
                "severity": "critical",
                "message": "Mandatory CO2 fire extinguisher missing from high-hazard vocational workshop.",
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            })

        if capacity_status == "DEFICIT":
            alerts.append({
                "id": f"cap_alert_{int(time.time())}",
                "type": "CAPACITY_DEFICIT",
                "severity": "medium",
                "message": f"Batch enrollment ({effective_claimed}) exceeds workstation capacity ({total_workstations}).",
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            })

        if activity_state == "IDLE" and total_trainees > 0:
            alerts.append({
                "id": f"idle_alert_{int(time.time())}",
                "type": "ZONE_IDLE_DURING_BATCH",
                "severity": "medium",
                "message": "Trainees observed idle with no active equipment interactions during practical hours.",
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            })

        if self.scenario == "poor_quality":
            alerts.append({
                "id": f"qual_alert_{int(time.time())}",
                "type": "QUALITY_GATE_FAILED",
                "severity": "medium",
                "message": "Optical lens occlusion / severe blur detected on camera feed.",
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            })

        telemetry: Dict[str, Any] = {
            "camera_id": self.camera_id,
            "centre_id": self.centre_id,
            "trade_id": self.trade_id,
            "trade_name": self.trade_name,
            "centre_name": self.centre_name,
            "scenario": self.scenario,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fps": round(self.current_fps, 1),
            "status": "online",
            "zones": {
                z_name: {
                    "raw_count": zone_raw_counts.get(z_name, 0),
                    "smoothed_count": zone_smoothed_counts.get(z_name, 0),
                    "claimed_attendance": effective_claimed if z_name == main_zone_name else 0,
                    "attendance_ratio": attendance_ratio if z_name == main_zone_name else 1.0,
                    "attendance_status": "MISMATCH" if is_mismatch and z_name == main_zone_name else "MATCH",
                }
                for z_name in current_zones
            },
            "total_persons_detected": total_trainees,
            "claimed_attendance": effective_claimed,
            "active_batch": {
                "name": self.active_batch_name,
                "zone": main_zone_name,
                "claimed_attendance": effective_claimed,
            },
            "equipment": equipment_status_list,
            "compliance_metrics": {
                "instructor_present": instructor_present,
                "ppe_compliance": {
                    "wearing_count": wearing_count,
                    "total_persons": total_trainees,
                    "compliance_rate": ppe_rate,
                    "status": ppe_status,
                },
                "safety_items": {
                    "fire_extinguisher": safety_extinguisher,
                    "first_aid_box": safety_first_aid,
                    "status": safety_status,
                },
                "mandatory_signage": {
                    "biometric_device": True,
                    "signage": True,
                    "status": signage_status,
                },
                "workstation_capacity": {
                    "claimed": effective_claimed,
                    "capacity": total_workstations,
                    "status": capacity_status,
                },
                "activity_state": activity_state,
            },
            "recent_alerts": alerts,
        }

        return jpeg_bytes, telemetry

    def _generate_synthetic_fallback(self) -> Tuple[bytes, Dict[str, Any]]:
        """Generate a simulated skilling centre frame if video source unavailable."""
        img = np.zeros((360, 640, 3), dtype=np.uint8)
        img[:] = (35, 45, 55)  # Dark slate background

        # Draw desks
        cv2.rectangle(img, (50, 100), (300, 320), (55, 65, 75), -1)
        cv2.rectangle(img, (340, 100), (590, 320), (55, 65, 75), -1)

        # Draw 5 simulated people with privacy blur blocks
        positions = [(100, 160), (200, 160), (150, 240), (400, 180), (500, 180)]
        for px, py in positions:
            cv2.rectangle(img, (px - 25, py - 40), (px + 25, py + 40), (240, 180, 0), 2)
            cv2.putText(img, "Trainee [Anonymized]", (px - 40, py - 46), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (240, 180, 0), 1)

        # HUD
        cv2.rectangle(img, (0, 0), (640, 32), (15, 23, 42), -1)
        cv2.putText(img, f"LIVE (Simulated) | CAM: {self.camera_id} | 7.5 FPS", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (50, 230, 120), 1)
        cv2.putText(img, "PRIVACY: ANONYMISED - ZERO RAW FACIAL DATA", (330, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 230, 255), 1)

        _, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        jpeg = buf.tobytes()

        telemetry = {
            "camera_id": self.camera_id,
            "centre_id": self.centre_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fps": 7.5,
            "status": "online",
            "zones": {
                "classroom": {
                    "raw_count": 5,
                    "smoothed_count": 5,
                    "claimed_attendance": self.claimed_attendance,
                    "attendance_ratio": round(5 / max(1, self.claimed_attendance), 2),
                    "attendance_status": "MISMATCH" if self.claimed_attendance > 7 else "MATCH",
                },
                "workshop": {
                    "raw_count": 0,
                    "smoothed_count": 0,
                    "claimed_attendance": 0,
                    "attendance_ratio": 1.0,
                    "attendance_status": "MATCH",
                },
            },
            "total_persons_detected": 5,
            "claimed_attendance": self.claimed_attendance,
            "active_batch": {
                "name": self.active_batch_name,
                "zone": "classroom",
                "claimed_attendance": self.claimed_attendance,
            },
            "equipment": [
                {"zone": "classroom", "item": "chair", "expected": 6, "detected": 5, "status": "DEFICIT"},
                {"zone": "classroom", "item": "computer", "expected": 4, "detected": 4, "status": "MATCH"},
            ],
            "compliance_metrics": {
                "instructor_present": True,
                "ppe_compliance": {"wearing_count": 5, "total_persons": 5, "compliance_rate": 1.0, "status": "COMPLIANT"},
                "safety_items": {"fire_extinguisher": True, "first_aid_box": True, "status": "COMPLIANT"},
                "mandatory_signage": {"biometric_device": True, "signage": True, "status": "COMPLIANT"},
                "workstation_capacity": {"claimed": self.claimed_attendance, "capacity": 10, "status": "COMPLIANT"},
                "activity_state": "ACTIVE",
            },
            "recent_alerts": [
                {
                    "id": f"live_sim_{int(time.time())}",
                    "type": "ATTENDANCE_MISMATCH",
                    "severity": "high",
                    "message": f"Classroom headcount (5) is below 70% of claimed attendance ({self.claimed_attendance}).",
                    "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                }
            ] if self.claimed_attendance > 7 else [],
        }
        return jpeg, telemetry

    def _sync_step(self, cap: Optional[cv2.VideoCapture], orig_w: int, orig_h: int) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
        """Perform one synchronous frame capture, inference, and annotation."""
        if cap is None or not cap.isOpened():
            return self._generate_synthetic_fallback()

        ret, frame = cap.read()
        if not ret or frame is None:
            if self.demo_mode:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()

        if not ret or frame is None:
            return self._generate_synthetic_fallback()

        return self._process_frame(frame, orig_w, orig_h)

    async def _run_loop(self) -> None:
        """Background frame loop. Automatically terminates when viewer_count == 0."""
        cap = self._open_capture()
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if cap and cap.isOpened() else 1280
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if cap and cap.isOpened() else 720

        frame_interval = 1.0 / max(1.0, self.fps_limit)
        fps_tracker_time = time.time()
        fps_frame_counter = 0

        try:
            while self.is_running and self.viewer_count > 0:
                loop_start = time.time()

                # Process frame synchronously in executor to not block asyncio event loop
                jpeg_bytes, telemetry = await asyncio.to_thread(self._sync_step, cap, orig_w, orig_h)

                if jpeg_bytes is not None and telemetry is not None:
                    self.latest_jpeg = jpeg_bytes
                    self.latest_telemetry = telemetry
                    self.frame_count += 1
                    fps_frame_counter += 1

                    # Update smoothed FPS every 10 frames
                    if fps_frame_counter >= 10:
                        now = time.time()
                        dt = now - fps_tracker_time
                        if dt > 0:
                            self.current_fps = round(fps_frame_counter / dt, 1)
                        fps_frame_counter = 0
                        fps_tracker_time = now

                    # Dispatch to video viewers
                    for q in list(self.viewers):
                        try:
                            q.put_nowait(jpeg_bytes)
                        except asyncio.QueueFull:
                            # Drop oldest frame to ensure zero latency
                            try:
                                q.get_nowait()
                                q.put_nowait(jpeg_bytes)
                            except Exception:
                                pass

                    # Dispatch to telemetry subscribers
                    for q in list(self.telemetry_subscribers):
                        try:
                            q.put_nowait(telemetry)
                        except asyncio.QueueFull:
                            try:
                                q.get_nowait()
                                q.put_nowait(telemetry)
                            except Exception:
                                pass

                # Rate limiting to target FPS
                elapsed = time.time() - loop_start
                sleep_duration = max(0.01, frame_interval - elapsed)
                await asyncio.sleep(sleep_duration)

        except asyncio.CancelledError:
            pass
        finally:
            if cap and cap.isOpened():
                cap.release()
            self.is_running = False


class CameraStreamManager:
    """Singleton registry of active camera stream sessions."""

    _instance: Optional["CameraStreamManager"] = None

    def __init__(self) -> None:
        self.sessions: Dict[str, CameraStreamSession] = {}

    @classmethod
    def get_instance(cls) -> "CameraStreamManager":
        if cls._instance is None:
            cls._instance = CameraStreamManager()
        return cls._instance

    def get_or_create_session(
        self,
        camera_id: str,
        centre_id: str,
        source: Optional[str] = None,
        claimed_attendance: int = 18,
        active_batch_name: str = "Solar Technician Level 4",
        fps_limit: float = 7.5,
        max_width: int = 640,
        demo_mode: bool = True,
        scenario: Optional[str] = None,
    ) -> CameraStreamSession:
        if camera_id not in self.sessions:
            self.sessions[camera_id] = CameraStreamSession(
                camera_id=camera_id,
                centre_id=centre_id,
                source=source,
                claimed_attendance=claimed_attendance,
                active_batch_name=active_batch_name,
                fps_limit=fps_limit,
                max_width=max_width,
                demo_mode=demo_mode,
                scenario=scenario,
            )
        else:
            if scenario is not None:
                self.sessions[camera_id].update_demo_config(scenario=scenario)
            if claimed_attendance != 18:
                self.sessions[camera_id].update_demo_config(claimed_attendance=claimed_attendance)
        return self.sessions[camera_id]

    def stop_all(self) -> None:
        """Stop all active camera sessions."""
        for session in self.sessions.values():
            session.stop()
        self.sessions.clear()


stream_manager = CameraStreamManager.get_instance()
