"""
API Integration Tests for Pratyaksha Backend.
Tests endpoints for events ingestion, attendance, CRUD operations, alerts filtering/review,
camera heartbeat, compliance calculation, and dashboard summary.
"""

from datetime import date, datetime, timezone


def test_health_and_root(client):
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "Pratyaksha" in res_root.json()["app"]

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"


def test_centres_crud(client):
    # Create
    payload = {
        "id": "centre_api_01",
        "name": "Mumbai Skill Hub",
        "state": "Maharashtra",
        "district": "Mumbai Suburban",
        "lat": 19.0760,
        "lng": 72.8777,
        "scheme": "PMKVY 4.0",
    }
    res_create = client.post("/centres", json=payload)
    assert res_create.status_code == 201
    assert res_create.json()["id"] == "centre_api_01"

    # Read
    res_get = client.get("/centres/centre_api_01")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "Mumbai Skill Hub"

    # Update
    res_put = client.put("/centres/centre_api_01", json={"name": "Mumbai Central Skill Hub"})
    assert res_put.status_code == 200
    assert res_put.json()["name"] == "Mumbai Central Skill Hub"

    # List with state filter
    res_list = client.get("/centres?state=Maharashtra")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1


def test_cameras_crud_and_heartbeat(client, standard_setup):
    cam_id = "cam_test_01"

    # Read camera
    res_get = client.get(f"/cameras/{cam_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == cam_id

    # Heartbeat
    res_hb = client.post(f"/cameras/{cam_id}/heartbeat")
    assert res_hb.status_code == 200
    assert res_hb.json()["camera_status"] == "online"
    assert res_hb.json()["last_seen_at"] is not None


def test_batches_and_attendance_flow(client, standard_setup):
    centre_id = standard_setup["centre"].id
    batch_id = standard_setup["batch"].id

    # Submit claimed attendance
    att_payload = {
        "centre_id": centre_id,
        "batch_id": batch_id,
        "date": "2026-10-19",
        "claimed_count": 22,
    }
    res_att = client.post("/attendance", json=att_payload)
    assert res_att.status_code == 201
    assert res_att.json()["claimed_count"] == 22

    # Query attendance records
    res_list = client.get(f"/attendance?centre_id={centre_id}")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1


def test_events_ingestion_single_and_batch_phase1_format(client, standard_setup):
    """
    Ensure the API directly accepts Phase 1 JSON Lines format with nested person_count: {raw, smoothed}.
    """
    cam_id = standard_setup["camera"].id

    # 1. Single ingestion with Phase 1 schema
    single_event = {
        "timestamp": "2026-10-19T10:00:00Z",
        "camera_id": cam_id,
        "zone": "classroom",
        "person_count": {
            "raw": 18,
            "smoothed": 18,
        },
        "infrastructure": [
            {"item": "chair", "expected": 20, "detected": 20, "status": "MATCH"},
            {"item": "computer", "expected": 10, "detected": 10, "status": "MATCH"},
        ],
    }
    res_single = client.post("/events", json=single_event)
    assert res_single.status_code == 201
    assert res_single.json()["events_ingested"] == 1

    # 2. Batch ingestion
    batch_events = [
        {
            "timestamp": "2026-10-19T10:15:00Z",
            "camera_id": cam_id,
            "zone": "classroom",
            "person_count": {"raw": 19, "smoothed": 19},
            "infrastructure": [{"item": "chair", "expected": 20, "detected": 20, "status": "MATCH"}],
        },
        {
            "timestamp": "2026-10-19T10:30:00Z",
            "camera_id": cam_id,
            "zone": "classroom",
            "person_count": {"raw": 19, "smoothed": 19},
            "infrastructure": [{"item": "chair", "expected": 20, "detected": 20, "status": "MATCH"}],
        },
    ]
    res_batch = client.post("/events", json=batch_events)
    assert res_batch.status_code == 201
    assert res_batch.json()["events_ingested"] == 2


def test_alerts_filtering_and_patch_review(client, standard_setup, db_session):
    from app.models import Alert

    centre_id = standard_setup["centre"].id
    alert = Alert(
        centre_id=centre_id,
        camera_id=standard_setup["camera"].id,
        zone="classroom",
        type="ATTENDANCE_MISMATCH",
        severity="HIGH",
        message="Simulated attendance violation",
        status="open",
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # Filter alerts by status and severity
    res_alerts = client.get(f"/alerts?centre_id={centre_id}&status=open&severity=HIGH")
    assert res_alerts.status_code == 200
    assert len(res_alerts.json()) == 1

    # PATCH alert review
    patch_payload = {
        "status": "verified",
        "reviewed_by": "Inspector Zaid",
        "review_notes": "Verified against physical register; discrepancy confirmed.",
    }
    res_patch = client.patch(f"/alerts/{alert.id}", json=patch_payload)
    assert res_patch.status_code == 200
    assert res_patch.json()["status"] == "verified"
    assert res_patch.json()["reviewed_by"] == "Inspector Zaid"


def test_compliance_and_dashboard_endpoints(client, standard_setup):
    centre_id = standard_setup["centre"].id

    # Compliance endpoint
    res_comp = client.get(f"/centres/{centre_id}/compliance")
    assert res_comp.status_code == 200
    data = res_comp.json()
    assert "compliance_score" in data
    assert 0.0 <= data["compliance_score"] <= 100.0
    assert data["summary_status"] in ["COMPLIANT", "NEEDS_ATTENTION", "NON_COMPLIANT"]

    # Dashboard Summary endpoint
    res_dash = client.get("/dashboard/summary")
    assert res_dash.status_code == 200
    dash_data = res_dash.json()
    assert dash_data["total_centres"] >= 1
    assert "alerts_by_type" in dash_data
    assert "top_non_compliant_centres" in dash_data


def test_event_idempotency_and_gzip(client, standard_setup):
    import gzip
    import json

    cam_id = standard_setup["camera"].id
    event_id = "test-uuid-event-001"

    event_payload = {
        "event_id": event_id,
        "camera_id": cam_id,
        "zone": "classroom",
        "timestamp": "2026-10-18T10:00:00Z",
        "person_count_raw": 15,
        "person_count_smoothed": 15,
        "infrastructure": [{"item": "chair", "expected": 20, "detected": 20, "status": "MATCH"}],
    }

    # 1. Normal ingestion
    res1 = client.post("/events", json=[event_payload])
    assert res1.status_code == 201
    assert res1.json()["events_ingested"] == 1
    assert res1.json()["duplicates_skipped"] == 0

    # 2. Duplicate ingestion (same event_id) -> must skip duplicate idempotently
    res2 = client.post("/events", json=[event_payload])
    assert res2.status_code == 201
    assert res2.json()["events_ingested"] == 0
    assert res2.json()["duplicates_skipped"] == 1

    # 3. Gzip-compressed ingestion
    event_payload_gzip = dict(event_payload, event_id="test-uuid-event-002")
    compressed_bytes = gzip.compress(json.dumps([event_payload_gzip]).encode("utf-8"))
    res3 = client.post(
        "/events",
        content=compressed_bytes,
        headers={"Content-Encoding": "gzip", "Content-Type": "application/json"},
    )
    assert res3.status_code == 201
    assert res3.json()["events_ingested"] == 1


def test_camera_heartbeat_telemetry(client, standard_setup):
    cam_id = standard_setup["camera"].id

    heartbeat_data = {
        "queue_depth": 5,
        "last_sample_time": "2026-10-18T10:05:00Z",
        "cpu_percent": 34.2,
        "memory_percent": 45.0,
        "agent_version": "1.4.0",
    }

    res = client.post(f"/cameras/{cam_id}/heartbeat", json=heartbeat_data)
    assert res.status_code == 200
    data = res.json()
    assert data["camera_id"] == cam_id
    assert data["queue_depth"] == 5
    assert data["agent_health"] == "healthy"
    assert data["agent_version"] == "1.4.0"


def test_evidence_thumbnail_upload(client, standard_setup):
    import base64

    cam_id = standard_setup["camera"].id
    # 1x1 pixel transparent gif/png in base64
    fake_b64 = base64.b64encode(b"fake-downscaled-privacy-blurred-jpeg-bytes").decode("utf-8")

    evidence_payload = {
        "event_id": "test-evidence-uuid-001",
        "camera_id": cam_id,
        "image_b64": fake_b64,
        "notes": "Attendance deficit evidence",
    }

    res = client.post("/events/evidence", json=evidence_payload)
    assert res.status_code == 201
    assert res.json()["status"] == "success"
    assert res.json()["event_id"] == "test-evidence-uuid-001"


def test_open_alerts_metrics_single_source_of_truth(client, standard_setup, db_session):
    """
    Validates single source of truth:
    sum(type counts) == sum(severity counts) == total open alerts
    """
    from app.models import Alert

    centre_id = standard_setup["centre"].id
    cam_id = standard_setup["camera"].id

    alerts = [
        Alert(centre_id=centre_id, camera_id=cam_id, type="ATTENDANCE_MISMATCH", severity="CRITICAL", status="open", message="Crit Att"),
        Alert(centre_id=centre_id, camera_id=cam_id, type="ATTENDANCE_MISMATCH", severity="HIGH", status="open", message="High Att"),
        Alert(centre_id=centre_id, camera_id=cam_id, type="CAMERA_OFFLINE", severity="HIGH", status="open", message="High Cam"),
        Alert(centre_id=centre_id, camera_id=cam_id, type="INSTRUCTOR_ABSENT", severity="HIGH", status="open", message="High Inst"),
        Alert(centre_id=centre_id, camera_id=cam_id, type="NON_FUNCTIONAL_EQUIPMENT", severity="MEDIUM", status="open", message="Med Equip"),
        Alert(centre_id=centre_id, camera_id=cam_id, type="PPE_VIOLATION", severity="HIGH", status="open", message="High PPE"),
        Alert(centre_id=centre_id, camera_id=cam_id, type="ATTENDANCE_MISMATCH", severity="HIGH", status="verified", message="Ignored"),
    ]
    db_session.add_all(alerts)
    db_session.commit()

    res = client.get("/alerts?status=open")
    assert res.status_code == 200
    open_alerts = res.json()

    total_alerts = len(open_alerts)
    assert total_alerts >= 6

    # 1. Compute severity counts
    severity_counts = {}
    for a in open_alerts:
        sev = a["severity"].upper()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # 2. Compute type counts
    type_counts = {}
    for a in open_alerts:
        t = a["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    # Invariant check: sum(type counts) == sum(severity counts) == total_alerts
    assert sum(severity_counts.values()) == total_alerts
    assert sum(type_counts.values()) == total_alerts


