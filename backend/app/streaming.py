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


class CameraStreamSession:
    """
    Manages live streaming and telemetry state for a single camera.
    Streaming runs ONLY while at least one viewer/telemetry subscriber is connected.
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
    ) -> None:
        self.camera_id = camera_id
        self.centre_id = centre_id
        self.source = source or "sample_data/skilling_center_demo.mp4"
        self.claimed_attendance = claimed_attendance
        self.active_batch_name = active_batch_name
        self.fps_limit = fps_limit
        self.max_width = max_width
        self.demo_mode = demo_mode

        # Zone configuration
        self.zones: Dict[str, Zone] = get_default_zones()

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

    def update_demo_config(self, claimed_attendance: Optional[int] = None, demo_mode: Optional[bool] = None) -> None:
        """Update live claimed attendance threshold or demo flag."""
        if claimed_attendance is not None:
            self.claimed_attendance = max(0, claimed_attendance)
        if demo_mode is not None:
            self.demo_mode = demo_mode

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
        2. Detect persons and equipment
        3. Enforce strict privacy: apply Gaussian blur to all persons
        4. Reconcile zones, attendance ratio, and equipment
        5. Draw clean visual HUD overlay
        6. Return encoded JPEG bytes and telemetry dictionary
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
        for p in person_dets:
            # Check foot point or center point
            pt = p.foot_point
            assigned = False
            for z_name, z in current_zones.items():
                if z.contains_point(pt):
                    zone_raw_counts[z_name] += 1
                    assigned = True
                    break
            # Fallback to center point if foot was just outside
            if not assigned:
                for z_name, z in current_zones.items():
                    if z.contains_point(p.center_point):
                        zone_raw_counts[z_name] += 1
                        break

        # Step 3: Update zone history and get smoothed counts
        zone_smoothed_counts: Dict[str, int] = {}
        for z_name, raw_c in zone_raw_counts.items():
            _, smoothed_c = self.zones[z_name].update_person_count(raw_c)
            zone_smoothed_counts[z_name] = smoothed_c

        # Step 4: Equipment count per zone
        zone_detected_infra: Dict[str, Dict[str, int]] = {z_name: {} for z_name in current_zones}
        for eq in equipment_dets:
            cpt = eq.center_point
            for z_name, z in current_zones.items():
                if z.contains_point(cpt):
                    item_type = eq.class_name
                    # Map COCO classes to common skilling inventory names
                    if item_type in ("laptop", "tv"):
                        item_type = "computer"
                    elif item_type in ("dining table", "bench"):
                        item_type = "workbench"
                    zone_detected_infra[z_name][item_type] = zone_detected_infra[z_name].get(item_type, 0) + 1
                    break

        # Evaluate equipment status
        equipment_status_list: List[Dict[str, Any]] = []
        for z_name, z in current_zones.items():
            results = z.evaluate_infrastructure(zone_detected_infra[z_name])
            for res in results:
                equipment_status_list.append({"zone": z_name, **res})

        # Step 5: Privacy Anonymization
        # Heavy Gaussian blur directly obliterating all faces and bodies
        annotated = ObjectDetector.apply_privacy_blur(resized, person_dets, kernel_size=39)

        # Step 6: Zone Visual Polygons & Tint
        overlay = annotated.copy()
        zone_colors = {
            "classroom": (245, 175, 45),  # Cyan-blue in BGR
            "workshop": (40, 200, 120),   # Green in BGR
        }
        for z_name, z in current_zones.items():
            color = zone_colors.get(z_name, (200, 150, 50))
            pts = z.polygon.reshape((-1, 1, 2))
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(annotated, [pts], isClosed=True, color=color, thickness=2)

            # Zone label pill
            if len(z.polygon) > 0:
                tx, ty = z.polygon[0]
                tag = f"ZONE: {z_name.upper()} ({zone_smoothed_counts[z_name]} trainees)"
                cv2.putText(
                    annotated,
                    tag,
                    (int(tx) + 6, max(22, int(ty) + 18)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.44,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    annotated,
                    tag,
                    (int(tx) + 6, max(22, int(ty) + 18)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.44,
                    (20, 20, 20),
                    1,
                    cv2.LINE_AA,
                )

        cv2.addWeighted(overlay, 0.22, annotated, 0.78, 0, annotated)

        # Step 7: Draw Infrastructure Detection Boxes
        for eq in equipment_dets:
            x1, y1, x2, y2 = eq.bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 220, 120), 1, cv2.LINE_AA)
            eq_label = f"{eq.class_name} {eq.confidence:.2f}"
            cv2.putText(
                annotated,
                eq_label,
                (x1, max(14, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (0, 220, 120),
                1,
                cv2.LINE_AA,
            )

        # Step 8: Draw Anonymous Person markers
        for p in person_dets:
            x1, y1, x2, y2 = p.bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (240, 180, 0), 2, cv2.LINE_AA)
            cv2.putText(
                annotated,
                "Trainee [Anonymized]",
                (x1, max(16, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.36,
                (240, 180, 0),
                1,
                cv2.LINE_AA,
            )

        # Step 9: Top HUD Overlay Bar
        hud_bar = annotated[:32, :].copy()
        cv2.rectangle(hud_bar, (0, 0), (new_w, 32), (15, 23, 42), -1)
        cv2.addWeighted(hud_bar, 0.85, annotated[:32, :], 0.15, 0, annotated[:32, :])

        # Status text left
        status_text = f"LIVE | CAM: {self.camera_id} | {self.current_fps:.1f} FPS | {new_w}x{new_h}"
        cv2.putText(
            annotated,
            status_text,
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (50, 230, 120),
            1,
            cv2.LINE_AA,
        )

        # Privacy badge right
        priv_text = "PRIVACY: ANONYMISED - ZERO RAW FACIAL DATA"
        (tw, _), _ = cv2.getTextSize(priv_text, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
        cv2.putText(
            annotated,
            priv_text,
            (max(10, new_w - tw - 12), 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (200, 230, 255),
            1,
            cv2.LINE_AA,
        )

        # Encode to JPEG
        _, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        jpeg_bytes = buffer.tobytes()

        # Step 10: Compute telemetry and alerts
        classroom_count = zone_smoothed_counts.get("classroom", 0)
        attendance_ratio = (
            round(classroom_count / float(self.claimed_attendance), 2)
            if self.claimed_attendance > 0
            else 1.0
        )
        is_mismatch = bool(self.claimed_attendance > 0 and classroom_count < 0.70 * self.claimed_attendance)

        alerts: List[Dict[str, Any]] = []
        if is_mismatch:
            alerts.append({
                "id": f"live_alert_{int(time.time())}",
                "type": "ATTENDANCE_MISMATCH",
                "severity": "high",
                "message": (
                    f"Classroom attendance deficit: {classroom_count} present vs {self.claimed_attendance} claimed "
                    f"({int(attendance_ratio * 100)}% of quota, below 70% threshold)."
                ),
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

        telemetry: Dict[str, Any] = {
            "camera_id": self.camera_id,
            "centre_id": self.centre_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fps": round(self.current_fps, 1),
            "status": "online",
            "zones": {
                z_name: {
                    "raw_count": zone_raw_counts.get(z_name, 0),
                    "smoothed_count": zone_smoothed_counts.get(z_name, 0),
                    "claimed_attendance": self.claimed_attendance if z_name == "classroom" else 0,
                    "attendance_ratio": attendance_ratio if z_name == "classroom" else 1.0,
                    "attendance_status": "MISMATCH" if is_mismatch and z_name == "classroom" else "MATCH",
                }
                for z_name in current_zones
            },
            "total_persons_detected": len(person_dets),
            "claimed_attendance": self.claimed_attendance,
            "active_batch": {
                "name": self.active_batch_name,
                "zone": "classroom",
                "claimed_attendance": self.claimed_attendance,
            },
            "equipment": equipment_status_list,
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
        demo_mode: bool = True,
    ) -> CameraStreamSession:
        if camera_id not in self.sessions:
            self.sessions[camera_id] = CameraStreamSession(
                camera_id=camera_id,
                centre_id=centre_id,
                source=source,
                claimed_attendance=claimed_attendance,
                active_batch_name=active_batch_name,
                fps_limit=fps_limit,
                demo_mode=demo_mode,
            )
        return self.sessions[camera_id]

    def stop_all(self) -> None:
        """Stop all active camera sessions."""
        for session in self.sessions.values():
            session.stop()
        self.sessions.clear()


stream_manager = CameraStreamManager.get_instance()
