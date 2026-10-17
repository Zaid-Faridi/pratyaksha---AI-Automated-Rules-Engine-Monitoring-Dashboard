"""
Application Configuration and Rules Thresholds for Pratyaksha Backend.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Details
    app_name: str = "Pratyaksha Video-Analytics Backend"
    environment: str = "development"
    debug: bool = True

    # Database: SQLite for development (default), switchable to PostgreSQL via env DATABASE_URL
    database_url: str = "sqlite:///./pratyaksha.db"

    # CORS
    cors_origins: List[str] = ["*"]

    # --- Rules Engine Configurable Thresholds ---
    # Attendance mismatch: flag if median smoothed count < 70% of claimed for N consecutive windows
    attendance_threshold_ratio: float = 0.70
    attendance_consecutive_windows: int = 3

    # Infrastructure gap: flag if item detected < expected for M consecutive samples
    infrastructure_consecutive_samples: int = 3

    # Camera health: offline if no events for X minutes during active batch window
    camera_offline_timeout_minutes: int = 15
    # Camera tamper: sudden drop in detected objects >= 80% while batch is active
    camera_tamper_drop_ratio: float = 0.80

    # Compliance score weights (summing to 1.0)
    compliance_weight_attendance: float = 0.45
    compliance_weight_infrastructure: float = 0.35
    compliance_weight_camera: float = 0.20

    # Privacy & Data Retention: delete raw events older than N days (default: 90 days)
    data_retention_days: int = 90

    # Edge API Key Authentication (Optional: when set, requires X-API-Key header on edge sync)
    edge_api_key: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
