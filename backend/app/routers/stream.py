"""
Streaming Router for Pratyaksha Live Video Analytics.
Provides endpoints for:
- MJPEG edge-annotated video streams per camera
- Fallback single-frame snapshots for low-bandwidth profiles
- Server-Sent Events (SSE) live telemetry channel (headcount, claimed quota, alerts, equipment)
- Dynamic demo configuration (claimed attendance threshold sweep)
- Centre-wide live streaming policy toggling
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pathlib import Path
from app.database import get_db
from app.models import Alert, AttendanceRecord, Batch, Camera, Centre
from app.streaming import stream_manager

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

router = APIRouter(tags=["Live Stream & Monitoring"])


class DemoConfigPayload(BaseModel):
    claimed_attendance: Optional[int] = None
    demo_mode: Optional[bool] = None
    scenario: Optional[str] = None


class CentreStreamingTogglePayload(BaseModel):
    enabled: bool


@router.get("/streaming/manifest")
def get_streaming_manifest():
    """Return master demo footage and scenario manifest for multi-centre monitoring."""
    manifest_paths = [
        ROOT_DIR / "demo_footage" / "manifest.json",
        ROOT_DIR / "demo_footage" / "manifest.yaml",
    ]
    for p in manifest_paths:
        if p.exists():
            if p.suffix == ".json":
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                import yaml
                with open(p, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
    raise HTTPException(status_code=404, detail="Demo footage manifest not found.")


@router.get("/streaming/wall")
def get_multi_centre_wall(db: Session = Depends(get_db)):
    """
    Return live status metadata for the 4-centre wall view grid:
    - Centre identification and trade profile
    - Primary camera ID and low-bandwidth stream URL
    - Current headcount vs claimed attendance
    - Real-time compliance score and active alerts count
    """
    target_centre_ids = ["centre_mh_01", "centre_up_02", "centre_ka_03", "centre_or_04"]
    centres = db.query(Centre).filter(Centre.id.in_(target_centre_ids)).all()
    if len(centres) < 4:
        centres = db.query(Centre).limit(4).all()

    # Sort in target order
    order_map = {cid: idx for idx, cid in enumerate(target_centre_ids)}
    centres.sort(key=lambda c: order_map.get(c.id, 99))

    wall_items = []
    for c in centres:
        cam = db.query(Camera).filter(Camera.centre_id == c.id).first()
        cam_id = cam.id if cam else f"cam_{c.id}"
        batch = db.query(Batch).filter(Batch.centre_id == c.id).first()
        active_alerts_count = db.query(Alert).filter(Alert.centre_id == c.id, Alert.status == "OPEN").count()

        session = stream_manager.sessions.get(cam_id)
        att_rec = db.query(AttendanceRecord).filter(AttendanceRecord.centre_id == c.id).order_by(AttendanceRecord.date.desc()).first()
        claimed_att = att_rec.claimed_count if att_rec else 15
        current_headcount = 0
        if session and session.latest_telemetry:
            current_headcount = session.latest_telemetry.get("total_persons_detected", 0)
            claimed_att = session.latest_telemetry.get("claimed_attendance", claimed_att)

        wall_items.append({
            "centre_id": c.id,
            "centre_name": c.name,
            "state": c.state,
            "district": c.district,
            "trade_id": c.trade_id or "general",
            "camera_id": cam_id,
            "stream_url": f"/api/cameras/{cam_id}/stream?max_width=480&fps=5.0",
            "snapshot_url": f"/api/cameras/{cam_id}/snapshot",
            "current_headcount": current_headcount,
            "claimed_attendance": claimed_att,
            "compliance_score": getattr(c, "compliance_score", 85.0) or 85.0,
            "active_alerts_count": active_alerts_count,
            "camera_status": cam.status if cam else "online",
            "current_scenario": session.scenario if session else "compliant",
        })

    return {
        "count": len(wall_items),
        "wall_centres": wall_items,
    }


@router.get("/cameras/{camera_id}/stream")
async def get_camera_stream(
    camera_id: str,
    claimed_attendance: Optional[int] = Query(None, description="Simulate or override claimed attendance quota"),
    demo: bool = Query(True, description="Enable looping demo video if physical RTSP is not connected"),
    scenario: Optional[str] = Query(None, description="Inject demo scenario (e.g. inflated_attendance, missing_machine, missing_ppe, instructor_absent, poor_quality, idle_session)"),
    max_width: int = Query(640, description="Max frame width for streaming bandwidth control"),
    fps: float = Query(7.5, description="Frame rate limit"),
    db: Session = Depends(get_db),
):
    """
    Serve live MJPEG video stream per camera with edge-rendered privacy blurring and zones.
    Stream starts only when a viewer connects, and automatically terminates when the viewer disconnects.
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    centre = db.query(Centre).filter(Centre.id == camera.centre_id).first()
    if centre and not getattr(centre, "live_streaming_enabled", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Live streaming is disabled for centre '{centre.name}' according to compliance policy.",
        )

    if camera.status == "offline" and not demo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera '{camera_id}' is offline and edge device is not sending heartbeats.",
        )

    # Resolve active batch and default claimed attendance
    batch = db.query(Batch).filter(Batch.centre_id == camera.centre_id).first()
    active_batch_name = batch.name if batch else "General Skilling Session"
    default_claimed = claimed_attendance if claimed_attendance is not None else (batch.expected_count if batch else 18)

    # Determine video source
    source = camera.rtsp_url
    if demo or not source or "internal" in str(source):
        source = "sample_data/skilling_center_demo.mp4"

    session = stream_manager.get_or_create_session(
        camera_id=camera_id,
        centre_id=camera.centre_id,
        source=source,
        claimed_attendance=default_claimed,
        active_batch_name=active_batch_name,
        fps_limit=fps,
        max_width=max_width,
        demo_mode=demo,
        scenario=scenario,
    )

    if claimed_attendance is not None or scenario is not None:
        session.update_demo_config(claimed_attendance=claimed_attendance, scenario=scenario)

    queue = await session.add_viewer()

    async def mjpeg_generator() -> AsyncGenerator[bytes, None]:
        try:
            while True:
                jpeg_bytes = await queue.get()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpeg_bytes)).encode("utf-8") + b"\r\n\r\n"
                    + jpeg_bytes
                    + b"\r\n"
                )
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            await session.remove_viewer(queue)

    return StreamingResponse(
        mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Privacy-Mode": "Anonymized-Edge-Only",
        },
    )


@router.get("/cameras/{camera_id}/snapshot")
async def get_camera_snapshot(
    camera_id: str,
    db: Session = Depends(get_db),
):
    """
    Fallback snapshot endpoint for low-bandwidth profiles or spot checks.
    Returns a single anonymized JPEG frame without maintaining a continuous MJPEG connection.
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    centre = db.query(Centre).filter(Centre.id == camera.centre_id).first()
    if centre and not getattr(centre, "live_streaming_enabled", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Live streaming is disabled for centre '{centre.name}' according to compliance policy.",
        )

    # Resolve source
    source = camera.rtsp_url
    if not source or "internal" in str(source) or not str(source).startswith("rtsp://"):
        source = "sample_data/skilling_center_demo.mp4"

    # Use existing session's latest JPEG if streaming, or generate one
    session = stream_manager.sessions.get(camera_id)
    if session and session.latest_jpeg:
        jpeg_bytes = session.latest_jpeg
    else:
        # Create temporary session to grab a single frame
        session = stream_manager.get_or_create_session(
            camera_id=camera_id,
            centre_id=camera.centre_id,
            source=source,
        )
        cap = session._open_capture()
        orig_w = int(cap.get(3)) if cap and cap.isOpened() else 1280
        orig_h = int(cap.get(4)) if cap and cap.isOpened() else 720
        jpeg_bytes, _ = session._sync_step(cap, orig_w, orig_h)
        if cap and cap.isOpened():
            cap.release()

    if not jpeg_bytes:
        raise HTTPException(status_code=500, detail="Failed to capture snapshot frame.")

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Privacy-Mode": "Anonymized-Edge-Only",
            "X-Snapshot-Time": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.get("/cameras/{camera_id}/telemetry")
async def get_camera_telemetry_stream(
    camera_id: str,
    db: Session = Depends(get_db),
):
    """
    Server-Sent Events (SSE) telemetry channel.
    Pushes live JSON packets: headcount per zone, claimed attendance comparison,
    equipment reconciliation, and newly raised compliance alerts.
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    centre = db.query(Centre).filter(Centre.id == camera.centre_id).first()
    if centre and not getattr(centre, "live_streaming_enabled", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Live streaming is disabled for centre '{centre.name}' according to compliance policy.",
        )

    batch = db.query(Batch).filter(Batch.centre_id == camera.centre_id).first()
    active_batch_name = batch.name if batch else "General Skilling Session"

    session = stream_manager.get_or_create_session(
        camera_id=camera_id,
        centre_id=camera.centre_id,
        source=camera.rtsp_url or "sample_data/skilling_center_demo.mp4",
        active_batch_name=active_batch_name,
    )

    queue = await session.add_telemetry_subscriber()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Send initial packet immediately if cached
            if session.latest_telemetry:
                yield f"data: {json.dumps(session.latest_telemetry)}\n\n"

            while True:
                telemetry = await queue.get()
                yield f"data: {json.dumps(telemetry)}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            await session.remove_telemetry_subscriber(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/cameras/{camera_id}/live-status")
def get_camera_live_status(
    camera_id: str,
    db: Session = Depends(get_db),
):
    """Query live camera streaming status, viewer count, and latest telemetry."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    centre = db.query(Centre).filter(Centre.id == camera.centre_id).first()
    streaming_allowed = getattr(centre, "live_streaming_enabled", True) if centre else True

    session = stream_manager.sessions.get(camera_id)
    return {
        "camera_id": camera_id,
        "centre_id": camera.centre_id,
        "camera_status": camera.status,
        "live_streaming_allowed": streaming_allowed,
        "is_streaming": session.is_running if session else False,
        "viewer_count": session.viewer_count if session else 0,
        "current_fps": session.current_fps if session else 0.0,
        "claimed_attendance": session.claimed_attendance if session else 18,
        "latest_telemetry": session.latest_telemetry if session else None,
    }


@router.post("/cameras/{camera_id}/demo-config")
def update_camera_demo_config(
    camera_id: str,
    payload: DemoConfigPayload,
    db: Session = Depends(get_db),
):
    """Dynamically adjust claimed attendance or demo mode for live demonstration."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    session = stream_manager.sessions.get(camera_id)
    if not session:
        session = stream_manager.get_or_create_session(
            camera_id=camera_id,
            centre_id=camera.centre_id,
            source=camera.rtsp_url or "sample_data/skilling_center_demo.mp4",
        )

    session.update_demo_config(
        claimed_attendance=payload.claimed_attendance,
        demo_mode=payload.demo_mode,
        scenario=payload.scenario,
    )

    return {
        "status": "success",
        "camera_id": camera_id,
        "claimed_attendance": session.claimed_attendance,
        "demo_mode": session.demo_mode,
        "scenario": getattr(session, "scenario", "compliant"),
    }


@router.put("/centres/{centre_id}/streaming")
def set_centre_streaming(
    centre_id: str,
    payload: CentreStreamingTogglePayload,
    db: Session = Depends(get_db),
):
    """Enable or disable live streaming entirely for a specific skilling centre."""
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre '{centre_id}' not found.")

    centre.live_streaming_enabled = payload.enabled
    db.commit()

    # If disabled, terminate any active camera sessions belonging to this centre
    if not payload.enabled:
        for cam in centre.cameras:
            if cam.id in stream_manager.sessions:
                stream_manager.sessions[cam.id].stop()

    return {
        "centre_id": centre_id,
        "centre_name": centre.name,
        "live_streaming_enabled": centre.live_streaming_enabled,
    }
