"""
Alerts Management and Review Router for Pratyaksha.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, AuditLog, utcnow
from app.schemas import AlertOut, AlertUpdate, AuditLogOut

router = APIRouter(prefix="/alerts", tags=["Compliance Alerts"])


@router.get("", response_model=List[AlertOut])
def list_alerts(
    centre_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    type: Optional[str] = Query(None, description="e.g. ATTENDANCE_MISMATCH, INFRASTRUCTURE_GAP, NON_FUNCTIONAL_EQUIPMENT, CAMERA_OFFLINE, CAMERA_TAMPER, POOR_CAMERA_QUALITY"),
    severity: Optional[str] = Query(None, description="LOW, MEDIUM, HIGH, CRITICAL, INFO"),
    status: Optional[str] = Query(None, description="open, verified, dismissed, auto_resolved"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    List compliance alerts with multi-dimensional filtering and pagination.
    """
    query = db.query(Alert)
    if centre_id:
        query = query.filter(Alert.centre_id == centre_id)
    if camera_id:
        query = query.filter(Alert.camera_id == camera_id)
    if type:
        query = query.filter(Alert.type == type)
    if severity:
        query = query.filter(Alert.severity == severity)
    if status:
        query = query.filter(Alert.status == status)
    if start_date:
        query = query.filter(Alert.created_at >= start_date)
    if end_date:
        query = query.filter(Alert.created_at <= end_date)

    return query.order_by(Alert.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    """Retrieve details for a specific alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return alert


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert_review(
    alert_id: int,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
):
    """
    Review, verify, or dismiss an alert with officer identification and immutable audit log entry.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    valid_statuses = ["open", "verified", "dismissed"]
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid alert status '{payload.status}'. Allowed values: {valid_statuses}",
        )

    officer = payload.officer_name or payload.reviewed_by or "Inspecting Officer"

    alert.status = payload.status
    alert.reviewed_at = utcnow()
    alert.reviewed_by = officer
    if payload.review_notes:
        alert.review_notes = payload.review_notes

    # Create immutable audit log record
    audit_entry = AuditLog(
        centre_id=alert.centre_id,
        alert_id=alert.id,
        officer_name=officer,
        action=payload.status.upper(),
        notes=payload.review_notes,
        timestamp=utcnow(),
    )
    db.add(audit_entry)

    db.commit()
    db.refresh(alert)
    return alert


@router.get("/{alert_id}/audit-trail", response_model=List[AuditLogOut])
def get_alert_audit_trail(
    alert_id: int,
    db: Session = Depends(get_db),
):
    """Fetch audit history specifically for this alert."""
    logs = db.query(AuditLog).filter(AuditLog.alert_id == alert_id).order_by(AuditLog.timestamp.desc()).all()
    return logs
