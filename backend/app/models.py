"""
SQLAlchemy ORM Data Models for Pratyaksha.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TradeProfile(Base):
    __tablename__ = "trade_profiles"

    id = Column(String(64), primary_key=True, index=True)  # e.g. "welding", "sewing", "it_lab", "electrical", "beauty_wellness", "retail"
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    sanctioned_equipment = Column(JSON, default=list)  # [{"item": "...", "expected_count": 10, "detector_prompts": [...], "operability": {...}}]
    required_ppe = Column(JSON, default=list)  # [{"name": "helmet", "required": true, "min_ratio": 0.8}]
    safety_items = Column(JSON, default=lambda: ["fire_extinguisher", "first_aid_box"])
    mandatory_signage = Column(JSON, default=lambda: ["safety_signage", "biometric_device"])
    workstation_capacity_rule = Column(JSON, default=dict)  # {"ratio": 1.0, "primary_item": "workbench"}
    compliance_checks = Column(JSON, default=dict)  # {"instructor_presence": true, "ppe_compliance": true, ...}
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    centres = relationship("Centre", back_populates="trade_profile")


class Centre(Base):
    __tablename__ = "centres"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    state = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    scheme = Column(String(100), nullable=False, default="PMKVY 4.0")
    trade_id = Column(String(64), ForeignKey("trade_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    trade_overrides = Column(JSON, default=dict)  # Zone-level overrides (e.g. {"zones": {"cutting_zone": {...}}})
    live_streaming_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    trade_profile = relationship("TradeProfile", back_populates="centres")
    cameras = relationship("Camera", back_populates="centre", cascade="all, delete-orphan")
    inventory = relationship("SanctionedInventory", back_populates="centre", cascade="all, delete-orphan")
    batches = relationship("Batch", back_populates="centre", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="centre", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="centre", cascade="all, delete-orphan")


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String(64), primary_key=True, index=True)
    centre_id = Column(String(64), ForeignKey("centres.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_names = Column(JSON, default=list)  # e.g. ["classroom", "workshop"]
    last_seen_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="offline")  # "online", "offline", "tampered"
    rtsp_url = Column(String(255), nullable=True)
    edge_metadata = Column(JSON, default=dict)  # {"queue_depth": 0, "cpu_percent": 12.5, "agent_version": "1.0.0"}
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    centre = relationship("Centre", back_populates="cameras")
    events = relationship("DetectionEvent", back_populates="camera", cascade="all, delete-orphan")


class SanctionedInventory(Base):
    __tablename__ = "sanctioned_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    centre_id = Column(String(64), ForeignKey("centres.id", ondelete="CASCADE"), nullable=False, index=True)
    zone = Column(String(100), nullable=False, index=True)
    item = Column(String(100), nullable=False, index=True)
    expected_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    centre = relationship("Centre", back_populates="inventory")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(String(64), primary_key=True, index=True)
    centre_id = Column(String(64), ForeignKey("centres.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    start_time = Column(String(8), nullable=False)  # "09:00"
    end_time = Column(String(8), nullable=False)    # "13:00"
    days = Column(JSON, default=list)  # e.g. ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    zone = Column(String(100), nullable=True, default="classroom")  # Primary active zone for batch
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    centre = relationship("Centre", back_populates="batches")
    attendance_records = relationship("AttendanceRecord", back_populates="batch", cascade="all, delete-orphan")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    centre_id = Column(String(64), ForeignKey("centres.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(String(64), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    claimed_count = Column(Integer, nullable=False)
    submitted_at = Column(DateTime, default=utcnow)

    # Relationships
    centre = relationship("Centre", back_populates="attendance_records")
    batch = relationship("Batch", back_populates="attendance_records")


class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=True, index=True)  # UUID from edge for idempotency
    camera_id = Column(String(64), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    zone = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    person_count_raw = Column(Integer, nullable=False)
    person_count_smoothed = Column(Integer, nullable=False)
    infrastructure = Column(JSON, default=list)  # [{"item": "chair", "expected": 6, "detected": 4, "status": "DEFICIT", "operability": "operational", "signals": {...}}]
    is_reliable = Column(Boolean, default=True, nullable=False)
    quality_metrics = Column(JSON, default=dict)
    compliance_metrics = Column(JSON, default=dict)  # Stores instructor_present, ppe_compliance, safety_items, signage, capacity, activity_state
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    camera = relationship("Camera", back_populates="events")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    centre_id = Column(String(64), ForeignKey("centres.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(String(64), nullable=True, index=True)
    zone = Column(String(100), nullable=True)
    item = Column(String(100), nullable=True)
    type = Column(String(64), nullable=False, index=True)  # ATTENDANCE_MISMATCH, INFRASTRUCTURE_GAP, NON_FUNCTIONAL_EQUIPMENT, CAMERA_OFFLINE, CAMERA_TAMPER, POOR_CAMERA_QUALITY
    severity = Column(String(32), nullable=False, index=True)  # LOW, MEDIUM, HIGH, CRITICAL, INFO
    message = Column(Text, nullable=False)
    evidence_thumbnail_path = Column(String(255), nullable=True)  # Pre-blurred only, privacy-preserving
    created_at = Column(DateTime, default=utcnow, index=True)
    status = Column(String(32), default="open", index=True)  # open, verified, dismissed, auto_resolved
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    # Relationships
    centre = relationship("Centre", back_populates="alerts")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    centre_id = Column(String(64), nullable=False, index=True)
    alert_id = Column(Integer, nullable=True, index=True)
    officer_name = Column(String(255), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)  # VERIFIED, DISMISSED, REOPENED, NOTE_ADDED, ATTENDANCE_SUBMITTED
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
