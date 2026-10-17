"""
Detection Events ingestion router for Pratyaksha.
Supports single and batch ingestion of Phase 1 JSONL formatted detections.
"""

import base64
import gzip
import json
import os
from pathlib import Path
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Alert, Camera, DetectionEvent, utcnow
from app.rules_engine import RulesEngine
from app.schemas import DetectionEventCreate, DetectionEventOut

router = APIRouter(prefix="/events", tags=["Detection Events"])


class EvidenceUploadPayload(BaseModel):
    event_id: str
    camera_id: str
    image_b64: str  # Base64 JPEG downscaled and privacy-blurred at edge
    notes: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def ingest_detection_events(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Ingest detection events directly from Phase 1/4 video detection pipelines.
    Supports single or batch events, gzip compressed payloads, idempotent event UUIDs,
    and optional API key authentication.
    """
    # 1. API key authentication check (if configured)
    if settings.edge_api_key and x_api_key != settings.edge_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )

    # 2. Decompress if payload is gzip-encoded
    content_encoding = request.headers.get("content-encoding", "").lower()
    raw_bytes = await request.body()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty request body.")

    try:
        if "gzip" in content_encoding:
            decompressed = gzip.decompress(raw_bytes)
            data = json.loads(decompressed.decode("utf-8"))
        else:
            data = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse JSON body: {str(exc)}")

    # 3. Normalize into list of DetectionEventCreate
    raw_list = data if isinstance(data, list) else [data]
    if not raw_list:
        raise HTTPException(status_code=400, detail="Empty events list.")

    events_list = [DetectionEventCreate(**item) for item in raw_list]

    inserted_records: List[DetectionEvent] = []
    duplicates_skipped = 0
    alerts_generated = []

    for item in events_list:
        # Idempotency check: if event_id is supplied and already recorded, skip duplicate
        if item.event_id:
            existing_event = db.query(DetectionEvent).filter(DetectionEvent.event_id == item.event_id).first()
            if existing_event:
                duplicates_skipped += 1
                continue

        camera = db.query(Camera).filter(Camera.id == item.camera_id).first()
        if not camera:
            raise HTTPException(
                status_code=404,
                detail=f"Camera with id '{item.camera_id}' not found. Please register camera first.",
            )

        # Update camera last seen time and status
        camera.last_seen_at = item.timestamp
        camera.status = "online"

        # Create DetectionEvent record
        db_event = DetectionEvent(
            event_id=item.event_id,
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
        "duplicates_skipped": duplicates_skipped,
        "alerts_evaluated": len(set(alerts_generated)),
    }


@router.post("/evidence", status_code=status.HTTP_201_CREATED)
def upload_evidence_thumbnail(
    payload: EvidenceUploadPayload,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Lazy upload of downscaled, privacy-blurred evidence thumbnail for an alert-worthy event.
    Stores the thumbnail and attaches it to relevant open alerts.
    """
    if settings.edge_api_key and x_api_key != settings.edge_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )

    evidence_dir = Path("outputs/evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    file_path = evidence_dir / f"{payload.event_id}.jpg"

    try:
        img_data = base64.b64decode(payload.image_b64)
        with open(file_path, "wb") as f:
            f.write(img_data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to decode evidence image: {str(exc)}")

    # Associate with open alerts for this camera
    recent_alerts = db.query(Alert).filter(
        Alert.camera_id == payload.camera_id,
        Alert.status == "open",
        Alert.evidence_thumbnail_path.is_(None),
    ).order_by(Alert.created_at.desc()).limit(3).all()

    for alert in recent_alerts:
        alert.evidence_thumbnail_path = str(file_path)

    db.commit()

    return {
        "status": "success",
        "event_id": payload.event_id,
        "evidence_path": str(file_path),
        "bytes_stored": len(img_data),
        "alerts_linked": len(recent_alerts),
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
