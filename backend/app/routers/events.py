"""
Detection Events ingestion router for Pratyaksha.
Supports single and batch ingestion of Phase 1 JSONL formatted detections.
"""

from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Camera, DetectionEvent, utcnow
from app.rules_engine import RulesEngine
from app.schemas import DetectionEventCreate, DetectionEventOut

router = APIRouter(prefix="/events", tags=["Detection Events"])


@router.post("", status_code=status.HTTP_201_CREATED)
def ingest_detection_events(
    payload: Union[DetectionEventCreate, List[DetectionEventCreate]],
    db: Session = Depends(get_db),
):
    """
    Ingest detection events directly from Phase 1 video detection pipelines.
    Accepts either a single event or a batch list of events.
    Triggers automated compliance rules evaluation upon ingestion.
    """
    events_list = [payload] if isinstance(payload, DetectionEventCreate) else payload
    if not events_list:
        raise HTTPException(status_code=400, detail="Empty events payload.")

    inserted_records: List[DetectionEvent] = []
    alerts_generated = []

    for item in events_list:
        camera = db.query(Camera).filter(Camera.id == item.camera_id).first()
        if not camera:
            # Auto-register camera or reject? Let's return informative error
            raise HTTPException(
                status_code=404,
                detail=f"Camera with id '{item.camera_id}' not found. Please register camera first.",
            )

        # Update camera last seen time and status
        camera.last_seen_at = item.timestamp
        camera.status = "online"

        # Create DetectionEvent record
        db_event = DetectionEvent(
            camera_id=item.camera_id,
            zone=item.zone,
            timestamp=item.timestamp,
            person_count_raw=item.person_count_raw or (item.person_count.raw if item.person_count else 0),
            person_count_smoothed=item.person_count_smoothed or (item.person_count.smoothed if item.person_count else 0),
            infrastructure=[infra.model_dump() for infra in item.infrastructure],
        )
        db.add(db_event)
        db.flush()  # assign ID
        inserted_records.append(db_event)

        # Execute rules engine checks for this event
        centre_id = camera.centre_id

        # 1. Attendance mismatch evaluation
        att_alert = RulesEngine.evaluate_attendance_mismatch(
            db=db,
            centre_id=centre_id,
            camera=camera,
            zone=item.zone,
            event_time=item.timestamp,
        )
        if att_alert:
            alerts_generated.append(att_alert.id)

        # 2. Infrastructure gap & surplus evaluation
        infra_alerts = RulesEngine.evaluate_infrastructure_discrepancies(
            db=db,
            centre_id=centre_id,
            camera=camera,
            zone=item.zone,
            event_time=item.timestamp,
            infra_items=db_event.infrastructure,
        )
        alerts_generated.extend([a.id for a in infra_alerts])

        # 3. Camera tamper evaluation
        tamper_alert = RulesEngine.evaluate_camera_tamper(
            db=db,
            centre_id=centre_id,
            camera=camera,
            zone=item.zone,
            event_time=item.timestamp,
            current_event=db_event,
        )
        if tamper_alert:
            alerts_generated.append(tamper_alert.id)

    db.commit()

    return {
        "status": "success",
        "events_ingested": len(inserted_records),
        "alerts_evaluated": len(set(alerts_generated)),
    }


@router.get("", response_model=List[DetectionEventOut])
def list_recent_events(
    camera_id: str = None,
    zone: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Retrieve recent detection events with optional camera and zone filters."""
    query = db.query(DetectionEvent)
    if camera_id:
        query = query.filter(DetectionEvent.camera_id == camera_id)
    if zone:
        query = query.filter(DetectionEvent.zone == zone)
    return query.order_by(DetectionEvent.timestamp.desc()).limit(limit).all()
