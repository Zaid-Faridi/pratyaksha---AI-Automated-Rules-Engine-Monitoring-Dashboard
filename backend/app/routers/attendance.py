"""
Claimed Attendance Submission router for Pratyaksha.
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AttendanceRecord, Batch, Camera, Centre, utcnow
from app.rules_engine import RulesEngine
from app.schemas import AttendanceCreate, AttendanceOut

router = APIRouter(prefix="/attendance", tags=["Claimed Attendance"])


@router.post("", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def submit_claimed_attendance(
    payload: AttendanceCreate,
    db: Session = Depends(get_db),
):
    """
    Submit officially claimed attendance for a training batch and date.
    Used by the rules engine to verify against actual detected attendance.
    """
    centre = db.query(Centre).filter(Centre.id == payload.centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{payload.centre_id}' not found.")

    batch = db.query(Batch).filter(Batch.id == payload.batch_id, Batch.centre_id == payload.centre_id).first()
    if not batch:
        raise HTTPException(
            status_code=404,
            detail=f"Batch '{payload.batch_id}' not found at centre '{payload.centre_id}'.",
        )

    # Check for existing record on that date (upsert behavior)
    record = db.query(AttendanceRecord).filter(
        AttendanceRecord.centre_id == payload.centre_id,
        AttendanceRecord.batch_id == payload.batch_id,
        AttendanceRecord.date == payload.date,
    ).first()

    if record:
        record.claimed_count = payload.claimed_count
        record.submitted_at = utcnow()
    else:
        record = AttendanceRecord(
            centre_id=payload.centre_id,
            batch_id=payload.batch_id,
            date=payload.date,
            claimed_count=payload.claimed_count,
            submitted_at=utcnow(),
        )
        db.add(record)

    db.commit()
    db.refresh(record)

    # Re-evaluate any active cameras in that zone
    cameras = db.query(Camera).filter(Camera.centre_id == payload.centre_id).all()
    for cam in cameras:
        zone = batch.zone or (cam.zone_names[0] if cam.zone_names else "classroom")
        RulesEngine.evaluate_attendance_mismatch(
            db=db,
            centre_id=payload.centre_id,
            camera=cam,
            zone=zone,
            event_time=utcnow(),
        )

    return record


@router.get("", response_model=List[AttendanceOut])
def list_attendance_records(
    centre_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    record_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """List claimed attendance submissions with optional filters."""
    query = db.query(AttendanceRecord)
    if centre_id:
        query = query.filter(AttendanceRecord.centre_id == centre_id)
    if batch_id:
        query = query.filter(AttendanceRecord.batch_id == batch_id)
    if record_date:
        query = query.filter(AttendanceRecord.date == record_date)
    return query.order_by(AttendanceRecord.date.desc(), AttendanceRecord.submitted_at.desc()).all()
