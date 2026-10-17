"""
Centre Management and Compliance Score Router for Pratyaksha.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Centre
from app.rules_engine import RulesEngine
from app.schemas import (
    CentreCreate,
    CentreOut,
    CentreUpdate,
    ComplianceBreakdown,
    CentreAttendanceHistory,
    ZoneInfrastructureStatus,
)

router = APIRouter(prefix="/centres", tags=["Centres & Compliance"])


@router.get("", response_model=List[CentreOut])
def list_centres(
    state: Optional[str] = None,
    district: Optional[str] = None,
    scheme: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all registered skilling centres with optional geographic filters."""
    query = db.query(Centre)
    if state:
        query = query.filter(Centre.state == state)
    if district:
        query = query.filter(Centre.district == district)
    if scheme:
        query = query.filter(Centre.scheme == scheme)
    return query.order_by(Centre.name).all()


@router.post("", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
def create_centre(
    payload: CentreCreate,
    db: Session = Depends(get_db),
):
    """Register a new skilling centre."""
    existing = db.query(Centre).filter(Centre.id == payload.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Centre with id '{payload.id}' already exists.")

    centre = Centre(**payload.model_dump())
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.get("/{centre_id}", response_model=CentreOut)
def get_centre(centre_id: str, db: Session = Depends(get_db)):
    """Retrieve details for a specific skilling centre."""
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{centre_id}' not found.")
    return centre


@router.put("/{centre_id}", response_model=CentreOut)
def update_centre(
    centre_id: str,
    payload: CentreUpdate,
    db: Session = Depends(get_db),
):
    """Update details of an existing skilling centre."""
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{centre_id}' not found.")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(centre, field, val)

    db.commit()
    db.refresh(centre)
    return centre


@router.delete("/{centre_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_centre(centre_id: str, db: Session = Depends(get_db)):
    """Delete a skilling centre and its associated inventory, cameras, and batches."""
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{centre_id}' not found.")

    db.delete(centre)
    db.commit()
    return None


@router.get("/{centre_id}/compliance", response_model=ComplianceBreakdown)
def get_centre_compliance(
    centre_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """
    Compute and return compliance score (0-100) and weighted breakdown for a centre:
    - Attendance match rate (45%)
    - Infrastructure availability rate (35%)
    - Camera uptime rate (20%)
    """
    try:
        breakdown = RulesEngine.calculate_compliance_score(
            db=db,
            centre_id=centre_id,
            start_date=start_date,
            end_date=end_date,
        )
        return breakdown
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{centre_id}/attendance-history", response_model=List[CentreAttendanceHistory])
def get_centre_attendance_history(centre_id: str, db: Session = Depends(get_db)):
    """
    Retrieve historical claimed vs observed attendance per batch and date for a centre,
    highlighting mismatch discrepancies.
    """
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{centre_id}' not found.")

    from app.models import AttendanceRecord, Batch, Camera, DetectionEvent
    import numpy as np
    from sqlalchemy import func

    records = db.query(AttendanceRecord).filter(AttendanceRecord.centre_id == centre_id).order_by(AttendanceRecord.date.asc()).all()
    history = []
    threshold = 0.70  # 70% threshold

    for r in records:
        batch = db.query(Batch).filter(Batch.id == r.batch_id).first()
        batch_name = batch.name if batch else r.batch_id

        # Find detected events for this date
        events = db.query(DetectionEvent).join(Camera).filter(
            Camera.centre_id == centre_id,
            func.date(DetectionEvent.timestamp) == r.date,
        ).all()

        observed_count = 0
        if events and batch:
            window_events = [e for e in events if RulesEngine.is_time_in_batch_window(batch, e.timestamp)]
            if window_events:
                observed_count = int(round(float(np.median([e.person_count_smoothed for e in window_events]))))
            else:
                observed_count = int(round(float(np.median([e.person_count_smoothed for e in events]))))
        elif events:
            observed_count = int(round(float(np.median([e.person_count_smoothed for e in events]))))

        ratio = observed_count / float(r.claimed_count) if r.claimed_count > 0 else 1.0
        is_mismatch = ratio < threshold

        history.append(
            CentreAttendanceHistory(
                date=r.date.isoformat(),
                batch_id=r.batch_id,
                batch_name=batch_name,
                claimed_count=r.claimed_count,
                detected_count=observed_count,
                mismatch=is_mismatch,
                ratio=round(ratio, 2),
            )
        )

    return history


@router.get("/{centre_id}/infrastructure-status", response_model=List[ZoneInfrastructureStatus])
def get_centre_infrastructure_status(centre_id: str, db: Session = Depends(get_db)):
    """
    Retrieve current detected vs expected equipment inventory by zone for a centre.
    """
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{centre_id}' not found.")

    from app.models import Camera, DetectionEvent, SanctionedInventory

    inventory_items = db.query(SanctionedInventory).filter(SanctionedInventory.centre_id == centre_id).all()
    results = []

    for item in inventory_items:
        latest_event = (
            db.query(DetectionEvent)
            .join(Camera)
            .filter(Camera.centre_id == centre_id, DetectionEvent.zone == item.zone)
            .order_by(DetectionEvent.timestamp.desc())
            .first()
        )

        detected = 0
        status_val = "DEFICIT"

        if latest_event and latest_event.infrastructure:
            entry = next((i for i in latest_event.infrastructure if i.get("item") == item.item), None)
            if entry:
                detected = entry.get("detected", 0)
                status_val = entry.get("status", "DEFICIT")
            else:
                detected = 0
                status_val = "DEFICIT"
        else:
            # Fallback if no events yet
            detected = item.expected_count
            status_val = "MATCH"

        results.append(
            ZoneInfrastructureStatus(
                zone=item.zone,
                item=item.item,
                expected=item.expected_count,
                detected=detected,
                status=status_val,
            )
        )

    return results

