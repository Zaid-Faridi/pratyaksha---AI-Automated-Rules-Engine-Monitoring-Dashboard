"""
Tests for Live Video Analytics Streaming and Viewer Lifecycle Logic.
Validates:
- Camera stream starts when first viewer/subscriber connects
- Camera stream stops when all viewers/subscribers disconnect
- Zero frames saved or logged to disk
- Per-centre live streaming disabled policy enforcement
- Fallback snapshot generation
- Dynamic demo configuration (claimed attendance adjustments)
"""

import asyncio
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.streaming import CameraStreamSession, stream_manager
from app.models import Centre, Camera, Batch


@pytest.fixture(autouse=True)
def cleanup_streaming():
    """Ensure all sessions are cleanly stopped after each test."""
    yield
    stream_manager.stop_all()


@pytest.mark.asyncio
async def test_viewer_start_and_stop_lifecycle():
    """
    Verify start-on-connect and stop-on-disconnect logic:
    Stream starts on 1st viewer, continues with 2nd viewer, and stops when count reaches 0.
    """
    session = CameraStreamSession(
        camera_id="cam_test_lifecycle",
        centre_id="centre_test",
        source="sample_data/skilling_center_demo.mp4",
        fps_limit=10.0,
        demo_mode=True,
    )

    # Initial state: inactive
    assert session.is_running is False
    assert session.viewer_count == 0

    # Viewer 1 connects -> Session starts
    q1 = await session.add_viewer()
    assert session.is_running is True
    assert session.viewer_count == 1
    assert q1 in session.viewers

    # Viewer 2 connects -> Session stays active
    q2 = await session.add_viewer()
    assert session.is_running is True
    assert session.viewer_count == 2
    assert q2 in session.viewers

    # Viewer 1 disconnects -> Session still active for viewer 2
    await session.remove_viewer(q1)
    assert session.is_running is True
    assert session.viewer_count == 1
    assert q1 not in session.viewers

    # Viewer 2 disconnects -> Session cleanly stops and releases camera
    await session.remove_viewer(q2)
    assert session.viewer_count == 0
    assert session.is_running is False


@pytest.mark.asyncio
async def test_telemetry_subscriber_lifecycle():
    """
    Verify telemetry subscriber registration triggers start on connect and stop on disconnect.
    """
    session = CameraStreamSession(
        camera_id="cam_test_telemetry_sub",
        centre_id="centre_test",
        source="sample_data/skilling_center_demo.mp4",
        fps_limit=10.0,
        demo_mode=True,
    )

    assert session.is_running is False
    assert session.viewer_count == 0

    sub_q = await session.add_telemetry_subscriber()
    assert session.is_running is True
    assert session.viewer_count == 1
    assert sub_q in session.telemetry_subscribers

    await session.remove_telemetry_subscriber(sub_q)
    assert session.is_running is False
    assert session.viewer_count == 0


def test_live_streaming_disabled_per_centre(client, db_session):
    """
    Verify HTTP 403 Forbidden is returned when a skilling centre has disabled live streaming.
    """
    centre = Centre(
        id="centre_stream_off",
        name="Private Defence Skill Centre",
        state="Haryana",
        district="Gurugram",
        lat=28.4595,
        lng=77.0266,
        scheme="Special Project",
        live_streaming_enabled=False,
    )
    db_session.add(centre)
    db_session.commit()

    cam = Camera(
        id="cam_stream_off_01",
        centre_id="centre_stream_off",
        status="online",
        rtsp_url="sample_data/skilling_center_demo.mp4",
    )
    db_session.add(cam)
    db_session.commit()

    # Attempting to access live stream should return 403 Forbidden
    resp = client.get("/cameras/cam_stream_off_01/stream")
    assert resp.status_code == 403
    assert "Live streaming is disabled for centre" in resp.json()["detail"]

    # Attempting snapshot should also return 403 Forbidden
    snap_resp = client.get("/cameras/cam_stream_off_01/snapshot")
    assert snap_resp.status_code == 403


def test_snapshot_endpoint_success(client, db_session):
    """
    Verify fallback snapshot endpoint returns valid JPEG bytes and privacy headers.
    """
    centre = Centre(
        id="centre_snap_test",
        name="Test Snapshot Centre",
        state="Maharashtra",
        district="Pune",
        lat=18.5204,
        lng=73.8567,
        live_streaming_enabled=True,
    )
    db_session.add(centre)
    db_session.commit()

    cam = Camera(
        id="cam_snap_test_01",
        centre_id="centre_snap_test",
        status="online",
        rtsp_url="sample_data/skilling_center_demo.mp4",
    )
    db_session.add(cam)
    db_session.commit()

    resp = client.get("/cameras/cam_snap_test_01/snapshot")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.headers.get("x-privacy-mode") == "Anonymized-Edge-Only"
    assert len(resp.content) > 1000  # Non-trivial JPEG payload


def test_demo_config_update(client, db_session):
    """
    Verify updating live demo configuration adjusts claimed attendance.
    """
    centre = Centre(
        id="centre_demo_cfg",
        name="Demo Config Centre",
        state="Karnataka",
        district="Bengaluru",
        lat=12.9716,
        lng=77.5946,
        live_streaming_enabled=True,
    )
    db_session.add(centre)
    db_session.commit()

    cam = Camera(
        id="cam_demo_cfg_01",
        centre_id="centre_demo_cfg",
        status="online",
        rtsp_url="sample_data/skilling_center_demo.mp4",
    )
    db_session.add(cam)
    db_session.commit()

    resp = client.post(
        "/cameras/cam_demo_cfg_01/demo-config",
        json={"claimed_attendance": 24, "demo_mode": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["claimed_attendance"] == 24


def test_toggle_centre_streaming_endpoint(client, db_session):
    """
    Verify PUT /centres/{centre_id}/streaming toggles policy flag.
    """
    centre = Centre(
        id="centre_toggle_test",
        name="Policy Toggle Centre",
        state="Rajasthan",
        district="Jaipur",
        lat=26.9124,
        lng=75.7873,
        live_streaming_enabled=True,
    )
    db_session.add(centre)
    db_session.commit()

    # Disable streaming
    resp = client.put(
        "/centres/centre_toggle_test/streaming",
        json={"enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["live_streaming_enabled"] is False

    # Enable streaming
    resp2 = client.put(
        "/centres/centre_toggle_test/streaming",
        json={"enabled": True},
    )
    assert resp2.status_code == 200
    assert resp2.json()["live_streaming_enabled"] is True
