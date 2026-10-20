"""
Edge Agent Configuration and Operating Profiles for Pratyaksha.
Loads settings from YAML files with environment variable overrides.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


@dataclass
class EdgeProfile:
    name: str
    sample_interval_sec: float
    input_resolution: int  # e.g. 320, 480, 640
    batch_size: int
    evidence_thumbnails_enabled: bool
    evidence_on_deficit_only: bool
    description: str


PROFILES: Dict[str, EdgeProfile] = {
    "ultra_low": EdgeProfile(
        name="ultra_low",
        sample_interval_sec=60.0,
        input_resolution=320,
        batch_size=20,
        evidence_thumbnails_enabled=False,
        evidence_on_deficit_only=False,
        description="Extreme bandwidth constraint (<256 Kbps / 2G). Metadata-only mode with 60s sampling.",
    ),
    "low": EdgeProfile(
        name="low",
        sample_interval_sec=30.0,
        input_resolution=480,
        batch_size=10,
        evidence_thumbnails_enabled=True,
        evidence_on_deficit_only=True,
        description="Rural 3G / intermittent connection. 30s sampling, thumbnails only on critical deficits.",
    ),
    "normal": EdgeProfile(
        name="normal",
        sample_interval_sec=15.0,
        input_resolution=640,
        batch_size=5,
        evidence_thumbnails_enabled=True,
        evidence_on_deficit_only=False,
        description="Semi-urban 4G/LTE or broadband (>2 Mbps). Standard 15s sampling with privacy thumbnails.",
    ),
}


@dataclass
class EdgeConfig:
    # Centre & Camera IDs
    centre_id: str = "centre_01"
    camera_id: str = "cam_01"
    source: str = "sample_data/skilling_center_demo.mp4"  # RTSP URL or local video path

    # Backend Connection
    backend_url: str = "http://127.0.0.1:8088"
    api_key: Optional[str] = None
    request_timeout_sec: float = 10.0

    # Operational Profile
    profile_name: str = "normal"  # "ultra_low", "low", "normal"

    # Offline Storage & Limits
    db_path: str = "edge/data/outbox.db"
    cache_path: str = "edge/data/schedule_cache.json"
    evidence_dir: str = "edge/data/evidence"
    log_file: str = "edge/data/edge.log"
    daily_budget_bytes: int = 50 * 1024 * 1024  # 50 MB / day

    # Telemetry and Intervals
    heartbeat_interval_sec: float = 60.0
    sync_interval_sec: float = 5.0
    schedule_refresh_interval_sec: float = 300.0  # 5 minutes

    # Camera Reconnect
    reconnect_initial_delay_sec: float = 2.0
    reconnect_max_delay_sec: float = 60.0
    reconnect_backoff_factor: float = 2.0

    # Adaptive Behavior Thresholds
    cpu_high_threshold: float = 85.0
    cpu_low_threshold: float = 50.0
    queue_high_threshold: int = 100
    queue_low_threshold: int = 15

    # Model
    model_path: str = "yolov8n.pt"
    onnx_path: str = "yolov8n.onnx"
    prefer_onnx: bool = True

    @property
    def profile(self) -> EdgeProfile:
        return PROFILES.get(self.profile_name, PROFILES["normal"])

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "EdgeConfig":
        """
        Load configuration from YAML file and apply environment variable overrides.
        """
        data: Dict[str, Any] = {}
        target_path = config_path or os.getenv("PRATYAKSHA_CONFIG_PATH", "edge/edge_config.yaml")

        if os.path.exists(target_path):
            with open(target_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        # Parse sections
        edge_section = data.get("edge", {})
        backend_section = data.get("backend", {})
        profile_section = data.get("adaptive", {})
        storage_section = data.get("storage", {})

        config = cls(
            centre_id=os.getenv("PRATYAKSHA_CENTRE_ID", edge_section.get("centre_id", "centre_01")),
            camera_id=os.getenv("PRATYAKSHA_CAMERA_ID", edge_section.get("camera_id", "cam_01")),
            source=os.getenv("PRATYAKSHA_CAMERA_SOURCE", edge_section.get("source", "sample_data/skilling_center_demo.mp4")),
            backend_url=os.getenv("BACKEND_URL", os.getenv("PRATYAKSHA_BACKEND_URL", backend_section.get("url", "http://127.0.0.1:8088"))).rstrip("/"),
            api_key=os.getenv("PRATYAKSHA_API_KEY", backend_section.get("api_key", None)),
            request_timeout_sec=float(backend_section.get("timeout_sec", 10.0)),
            profile_name=os.getenv("PRATYAKSHA_PROFILE", profile_section.get("profile", "normal")),
            db_path=storage_section.get("db_path", "edge/data/outbox.db"),
            cache_path=storage_section.get("cache_path", "edge/data/schedule_cache.json"),
            evidence_dir=storage_section.get("evidence_dir", "edge/data/evidence"),
            log_file=storage_section.get("log_file", "edge/data/edge.log"),
            daily_budget_bytes=int(storage_section.get("daily_budget_bytes", 50 * 1024 * 1024)),
        )

        return config
