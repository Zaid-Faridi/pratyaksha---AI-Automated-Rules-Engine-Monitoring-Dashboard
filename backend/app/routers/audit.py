"""
Audit Trail Router for Pratyaksha.
Tracks officer reviews, verifications, dismissals, and attendance submissions.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, utcnow
from app.schemas import AuditLogCreate, AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["Audit Trail"])


@router.get("", response_model=List[AuditLogOut])
def list_audit_logs(
    centre_id: Optional[str] = None,
    officer_name: Optional[str] = None,
    action: Optional[str] = None,
    alert_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    List audit logs with filtering by centre, officer, action, or alert.
    """
    query = db.query(AuditLog)
    if centre_id:
        query = query.filter(AuditLog.centre_id == centre_id)
    if officer_name:
        query = query.filter(AuditLog.officer_name.ilike(f"%{officer_name}%"))
    if action:
        query = query.filter(AuditLog.action == action.upper())
    if alert_id:
        query = query.filter(AuditLog.alert_id == alert_id)

    return query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=AuditLogOut, status_code=status.HTTP_201_CREATED)
def create_audit_log(
    payload: AuditLogCreate,
    db: Session = Depends(get_db),
):
    """
    Manually record an audit action (e.g., portal attendance submission or offline audit note).
    """
    log_entry = AuditLog(
        centre_id=payload.centre_id,
        alert_id=payload.alert_id,
        officer_name=payload.officer_name,
        action=payload.action.upper(),
        notes=payload.notes,
        timestamp=utcnow(),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
