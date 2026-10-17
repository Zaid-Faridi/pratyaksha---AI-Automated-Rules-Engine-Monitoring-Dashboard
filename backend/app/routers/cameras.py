"""
Camera Management and Health Heartbeat Router for Pratyaksha.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, Camera, Centre, utcnow
from app.schemas import CameraCreate, CameraOut, CameraUpdate

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("", response_model=List[CameraOut])
def list_cameras(
    centre_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all registered cameras with optional centre and status filters."""
    query = db.query(Camera)
    if centre_id:
        query = query.filter(Camera.centre_id == centre_id)
    if status:
        query = query.filter(Camera.status == status)
    return query.order_by(Camera.id).all()


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
):
    """Register a new camera under a centre."""
    centre = db.query(Centre).filter(Centre.id == payload.centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{payload.centre_id}' not found.")

    existing = db.query(Camera).filter(Camera.id == payload.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Camera with id '{payload.id}' already exists.")

    camera = Camera(**payload.model_dump())
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    """Retrieve details for a specific camera."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    return camera


@router.put("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: str,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
):
    """Update camera configuration and zones."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(camera, field, val)

    db.commit()
    db.refresh(camera)
    return camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    """Delete a camera."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    db.delete(camera)
    db.commit()
    return None


@router.post("/{camera_id}/heartbeat")
def camera_heartbeat(camera_id: str, db: Session = Depends(get_db)):
    """
    Heartbeat ping from camera edge device.
    Updates last_seen_at timestamp, marks camera online, and auto-resolves any offline alerts.
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    now = utcnow()
    camera.last_seen_at = now
    camera.status = "online"

    # Auto-resolve any open CAMERA_OFFLINE alert
    open_alert = db.query(Alert).filter(
        Alert.camera_id == camera_id,
        Alert.type == "CAMERA_OFFLINE",
        Alert.status == "open",
    ).first()
    if open_alert:
        open_alert.status = "auto_resolved"
        open_alert.review_notes = "Auto-resolved: Heartbeat received."
        open_alert.reviewed_at = now

    db.commit()

    return {
        "status": "success",
        "camera_id": camera_id,
        "camera_status": camera.status,
        "last_seen_at": camera.last_seen_at,
    }
