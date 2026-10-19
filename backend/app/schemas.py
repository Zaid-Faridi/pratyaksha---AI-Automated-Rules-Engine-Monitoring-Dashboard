"""
Pydantic Schemas for Request/Response Validation in Pratyaksha Backend.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator


# --- Infrastructure Schemas ---

class InfrastructureItem(BaseModel):
    item: str
    expected: int
    detected: int
    status: str  # "MATCH", "DEFICIT", "SURPLUS"
    operability: Optional[str] = "operational"  # "operational", "uncertain", "non_operational", "missing"
    signals: Optional[Dict[str, Any]] = None


class PersonCountObject(BaseModel):
    raw: int
    smoothed: int


# --- Detection Event Schemas (Matches Phase 1 JSONL output format) ---

class DetectionEventCreate(BaseModel):
    event_id: Optional[str] = None  # UUID for idempotent edge sync
    timestamp: datetime
    camera_id: str
    zone: str
    # Support Phase 1 nested object: person_count: {raw: int, smoothed: int}
    person_count: Optional[PersonCountObject] = None
    # Or flat parameters
    person_count_raw: Optional[int] = None
    person_count_smoothed: Optional[int] = None
    infrastructure: List[InfrastructureItem] = Field(default_factory=list)
    is_reliable: Optional[bool] = True
    quality_metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    compliance_metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="before")
    def normalize_person_count(cls, data: Any) -> Any:
        if isinstance(data, dict):
            pcount = data.get("person_count")
            if isinstance(pcount, dict):
                data["person_count_raw"] = pcount.get("raw", 0)
                data["person_count_smoothed"] = pcount.get("smoothed", 0)
            elif data.get("person_count_raw") is not None and data.get("person_count_smoothed") is not None:
                data["person_count"] = {
                    "raw": data["person_count_raw"],
                    "smoothed": data["person_count_smoothed"],
                }
        return data


class DetectionEventOut(BaseModel):
    id: int
    event_id: Optional[str] = None
    camera_id: str
    zone: str
    timestamp: datetime
    person_count_raw: int
    person_count_smoothed: int
    infrastructure: List[Dict[str, Any]]
    is_reliable: bool = True
    quality_metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    compliance_metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CameraHeartbeatPayload(BaseModel):
    queue_depth: Optional[int] = 0
    last_sample_time: Optional[datetime] = None
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    agent_version: Optional[str] = "1.0.0"



# --- Trade Profile Schemas ---

class TradeProfileBase(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    sanctioned_equipment: List[Dict[str, Any]] = Field(default_factory=list)
    required_ppe: List[Any] = Field(default_factory=list)
    safety_items: List[Any] = Field(default_factory=list)
    mandatory_signage: List[Any] = Field(default_factory=list)
    workstation_capacity_rule: Dict[str, Any] = Field(default_factory=dict)
    compliance_checks: Dict[str, Any] = Field(default_factory=dict)


class TradeProfileCreate(TradeProfileBase):
    id: str


class TradeProfileUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    sanctioned_equipment: Optional[List[Dict[str, Any]]] = None
    required_ppe: Optional[List[Dict[str, Any]]] = None
    safety_items: Optional[List[Any]] = None
    mandatory_signage: Optional[List[Any]] = None
    workstation_capacity_rule: Optional[Dict[str, Any]] = None
    compliance_checks: Optional[Dict[str, Any]] = None


class TradeProfileOut(TradeProfileBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- Centre Schemas ---

class CentreBase(BaseModel):
    name: str
    state: str
    district: str
    lat: float
    lng: float
    scheme: str = "PMKVY 4.0"
    trade_id: Optional[str] = None
    trade_overrides: Optional[Dict[str, Any]] = Field(default_factory=dict)
    live_streaming_enabled: bool = True


class CentreCreate(CentreBase):
    id: str


class CentreUpdate(BaseModel):
    name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    scheme: Optional[str] = None
    trade_id: Optional[str] = None
    trade_overrides: Optional[Dict[str, Any]] = None
    live_streaming_enabled: Optional[bool] = None


class CentreOut(CentreBase):
    id: str
    created_at: datetime
    trade_profile: Optional[TradeProfileOut] = None

    model_config = ConfigDict(from_attributes=True)


# --- Camera Schemas ---

class CameraBase(BaseModel):
    centre_id: str
    zone_names: List[str] = Field(default_factory=list)
    rtsp_url: Optional[str] = None


class CameraCreate(CameraBase):
    id: str


class CameraUpdate(BaseModel):
    centre_id: Optional[str] = None
    zone_names: Optional[List[str]] = None
    status: Optional[str] = None
    rtsp_url: Optional[str] = None


class CameraOut(CameraBase):
    id: str
    status: str
    last_seen_at: Optional[datetime] = None
    edge_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Sanctioned Inventory Schemas ---

class SanctionedInventoryBase(BaseModel):
    centre_id: str
    zone: str
    item: str
    expected_count: int = Field(ge=0)


class SanctionedInventoryCreate(SanctionedInventoryBase):
    pass


class SanctionedInventoryUpdate(BaseModel):
    zone: Optional[str] = None
    item: Optional[str] = None
    expected_count: Optional[int] = None


class SanctionedInventoryOut(SanctionedInventoryBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Batch Schemas ---

class BatchBase(BaseModel):
    centre_id: str
    name: str
    start_time: str = Field(description="24-hour HH:MM format, e.g. '09:00'")
    end_time: str = Field(description="24-hour HH:MM format, e.g. '13:00'")
    days: List[str] = Field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    zone: Optional[str] = "classroom"


class BatchCreate(BatchBase):
    id: str


class BatchUpdate(BaseModel):
    name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    days: Optional[List[str]] = None
    zone: Optional[str] = None


class BatchOut(BatchBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Attendance Record Schemas ---

class AttendanceCreate(BaseModel):
    centre_id: str
    batch_id: str
    date: date
    claimed_count: int = Field(ge=0)


class AttendanceOut(BaseModel):
    id: int
    centre_id: str
    batch_id: str
    date: date
    claimed_count: int
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Alert Schemas ---

class AlertOut(BaseModel):
    id: int
    centre_id: str
    camera_id: Optional[str] = None
    zone: Optional[str] = None
    item: Optional[str] = None
    type: str
    severity: str
    message: str
    evidence_thumbnail_path: Optional[str] = None
    created_at: datetime
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AlertUpdate(BaseModel):
    status: str = Field(description="'verified', 'dismissed', or 'open'")
    reviewed_by: Optional[str] = None
    officer_name: Optional[str] = None
    review_notes: Optional[str] = None


class AuditLogCreate(BaseModel):
    centre_id: str
    alert_id: Optional[int] = None
    officer_name: str
    action: str
    notes: Optional[str] = None


class AuditLogOut(BaseModel):
    id: int
    centre_id: str
    alert_id: Optional[int] = None
    officer_name: str
    action: str
    notes: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Compliance & Dashboard Analytics Schemas ---

class ComplianceBreakdown(BaseModel):
    centre_id: str
    centre_name: str
    compliance_score: float  # 0 - 100
    attendance_rate: float   # 0.0 - 1.0 (or percentage)
    infrastructure_availability_rate: float
    camera_uptime_rate: float
    open_alerts_count: int
    weights: Dict[str, float]
    summary_status: str      # "COMPLIANT", "NEEDS_ATTENTION", "NON_COMPLIANT"


class DashboardSummary(BaseModel):
    total_centres: int
    total_cameras: int
    online_cameras: int
    offline_cameras: int
    total_batches: int
    total_claimed_attendance: int
    total_observed_attendance: int
    open_alerts_count: int
    alerts_by_type: Dict[str, int]
    alerts_by_severity: Dict[str, int]
    top_non_compliant_centres: List[ComplianceBreakdown]
    average_compliance_score: float = 0.0
    attendance_mismatches_today: int = 0
    compliance_trend: List[Dict[str, Any]] = Field(default_factory=list)


class CentreAttendanceHistory(BaseModel):
    date: str
    batch_id: str
    batch_name: str
    claimed_count: int
    detected_count: int
    mismatch: bool
    ratio: float


class ZoneInfrastructureStatus(BaseModel):
    zone: str
    item: str
    expected: int
    detected: int
    status: str

