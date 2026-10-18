"""
Unit and Integration Tests for:
1. Apparent Operability Assessment (Heuristics & History Tracker)
2. Frame Quality Gating (Blur, Brightness, Obstruction & Rule Gating)
3. New Alert Types (NON_FUNCTIONAL_EQUIPMENT, POOR_CAMERA_QUALITY)
4. Audit Trail Logging
5. Ministry-ready Reports Export (CSV & PDF)
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from operability import (
    OperabilityAssessment,
    OperabilityEvaluator,
    OperabilityHistoryTracker,
    OPERABILITY_DISCLAIMER,
)
from quality import (
    FrameQualityResult,
    FrameQualityEvaluator,
    evaluate_frame_quality,
)
from app.models import Alert, AuditLog, Camera, Centre, DetectionEvent, utcnow
from app.rules_engine import RulesEngine


# --- 1. Operability Heuristics Tests ---

def test_screen_on_detection_heuristics():
    h, w = 200, 300
    frame = np.zeros((h, w, 3), dtype=np.uint8)

    # Bright active screen box (luminescence ~180, high variance)
    frame[50:150, 50:200] = np.random.randint(140, 220, size=(100, 150, 3), dtype=np.uint8)
    bbox_on = (50, 50, 200, 150)

    res_on = OperabilityEvaluator.evaluate_computer(frame, bbox_on, has_person_proximate=True)
    assert res_on.status == "operational"
    assert res_on.signals.get("screen_on") is True

    # Off / black screen box
    frame[50:150, 50:200] = 5  # very dark
    res_off = OperabilityEvaluator.evaluate_computer(frame, bbox_on, has_person_proximate=False)
    assert res_off.status == "non_operational"
    assert res_off.signals.get("screen_on") is False


def test_machine_proximity_and_tarp_heuristics():
    # Textured uncovered machine
    frame = np.random.randint(60, 180, size=(400, 400, 3), dtype=np.uint8)
    lathe_box = (100, 100, 250, 250)

    # Case A: Person working right next to machine
    res = OperabilityEvaluator.evaluate_machine(frame, lathe_box, "lathe", has_person_proximate=True)
    assert res.status == "operational"
    assert res.signals.get("trainee_proximate") is True

    # Case B: Machine covered by uniform tarp (low variance)
    frame_tarp = np.ones((400, 400, 3), dtype=np.uint8) * 120
    res_tarp = OperabilityEvaluator.evaluate_machine(frame_tarp, lathe_box, "lathe", has_person_proximate=False)
    assert res_tarp.status == "non_operational"
    assert res_tarp.signals.get("is_covered_with_tarp") is True


def test_operability_history_temporal_smoothing():
    tracker = OperabilityHistoryTracker(history_len=5, consecutive_threshold=3)

    # 1 sample non_op -> effective status remains uncertain / 1 sample
    eff1, count1 = tracker.update("cam_01", "workshop", "lathe", "non_operational")
    assert eff1 == "uncertain"
    assert count1 == 1

    # 2nd sample non_op
    eff2, count2 = tracker.update("cam_01", "workshop", "lathe", "non_operational")
    assert eff2 == "uncertain"
    assert count2 == 2

    # 3rd sample non_op -> confirmed non_operational
    eff3, count3 = tracker.update("cam_01", "workshop", "lathe", "non_operational")
    assert eff3 == "non_operational"
    assert count3 == 3

    # Operational sample arrives -> clears to operational
    eff4, count4 = tracker.update("cam_01", "workshop", "lathe", "operational")
    assert eff4 == "operational"
    assert count4 == 0


# --- 2. Frame Quality Gating Tests ---

def test_frame_quality_evaluation():
    # Good, clear frame
    clear_frame = np.random.randint(50, 200, size=(240, 320, 3), dtype=np.uint8)
    q_good = evaluate_frame_quality(clear_frame)
    assert q_good.is_reliable is True
    assert q_good.blur_laplacian > 45.0

    # Severe blur frame
    blurred_frame = np.ones((240, 320, 3), dtype=np.uint8) * 120
    q_blur = evaluate_frame_quality(blurred_frame)
    assert q_blur.is_reliable is False
    assert "BLURRY_OUT_OF_FOCUS" in q_blur.issues

    # Extremely dark frame
    dark_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    q_dark = evaluate_frame_quality(dark_frame)
    assert q_dark.is_reliable is False
    assert "TOO_DARK" in q_dark.issues


def test_frame_quality_tracker_consecutive_trigger():
    evaluator = FrameQualityEvaluator()
    camera_id = "cam_test_consec"

    # 1st and 2nd bad samples
    dark_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    res1 = evaluator.evaluate_frame(dark_frame, camera_id=camera_id)
    assert res1.is_reliable is False
    assert evaluator.consecutive_unreliable[camera_id] == 1

    res2 = evaluator.evaluate_frame(dark_frame, camera_id=camera_id)
    assert evaluator.consecutive_unreliable[camera_id] == 2

    # 3rd bad sample
    res3 = evaluator.evaluate_frame(dark_frame, camera_id=camera_id)
    assert evaluator.consecutive_unreliable[camera_id] == 3

    # Clean frame arrives -> resets to 0
    clear_frame = np.random.randint(50, 200, size=(240, 320, 3), dtype=np.uint8)
    res_clear = evaluator.evaluate_frame(clear_frame, camera_id=camera_id)
    assert res_clear.is_reliable is True
    assert evaluator.consecutive_unreliable[camera_id] == 0


# --- 3. Rules Engine Integration Tests ---

def test_quality_gating_and_alert_in_rules_engine(db_session):
    # Setup test centre and camera
    centre = Centre(id="centre_test_q", name="Quality Test Centre", state="Delhi", district="Central", lat=28.6, lng=77.2)
    db_session.add(centre)
    camera = Camera(id="cam_test_q", centre_id="centre_test_q", zone_names=["workshop"], status="online")
    db_session.add(camera)
    db_session.commit()

    now = utcnow()

    # Ingest 3 consecutive unreliable events
    for i in range(3):
        ev = DetectionEvent(
            camera_id="cam_test_q",
            zone="workshop",
            timestamp=now + timedelta(seconds=i * 10),
            person_count_raw=0,
            person_count_smoothed=0,
            is_reliable=False,
            quality_metrics={"issues": ["severe_blur", "underexposed"]},
        )
        db_session.add(ev)
        db_session.commit()

        alert = RulesEngine.evaluate_camera_quality(
            db=db_session,
            centre_id="centre_test_q",
            camera=camera,
            zone="workshop",
            event_time=ev.timestamp,
            current_event=ev,
        )

    # Verify POOR_CAMERA_QUALITY alert was raised
    assert alert is not None
    assert alert.type == "POOR_CAMERA_QUALITY"
    assert alert.severity == "HIGH"
    assert alert.status == "open"

    # Frame quality recovers -> Auto-resolve
    good_ev = DetectionEvent(
        camera_id="cam_test_q",
        zone="workshop",
        timestamp=now + timedelta(seconds=40),
        person_count_raw=10,
        person_count_smoothed=10,
        is_reliable=True,
    )
    db_session.add(good_ev)
    db_session.commit()

    RulesEngine.evaluate_camera_quality(
        db=db_session,
        centre_id="centre_test_q",
        camera=camera,
        zone="workshop",
        event_time=good_ev.timestamp,
        current_event=good_ev,
    )

    db_session.refresh(alert)
    assert alert.status == "auto_resolved"


def test_apparent_operability_alert_in_rules_engine(db_session):
    centre = Centre(id="centre_test_op", name="Operability Test Centre", state="UP", district="Lucknow", lat=26.8, lng=80.9)
    db_session.add(centre)
    camera = Camera(id="cam_test_op", centre_id="centre_test_op", zone_names=["workshop"], status="online")
    db_session.add(camera)
    db_session.commit()

    now = utcnow()

    # 3 consecutive events where lathe is non_operational
    infra_non_op = [{
        "item": "lathe",
        "expected": 2,
        "detected": 2,
        "operability": "non_operational",
        "signals": {"covered_or_stacked": True},
    }]

    for i in range(3):
        ev = DetectionEvent(
            camera_id="cam_test_op",
            zone="workshop",
            timestamp=now + timedelta(seconds=i * 10),
            person_count_raw=5,
            person_count_smoothed=5,
            infrastructure=infra_non_op,
            is_reliable=True,
        )
        db_session.add(ev)
        db_session.commit()

        op_alerts = RulesEngine.evaluate_apparent_operability(
            db=db_session,
            centre_id="centre_test_op",
            camera=camera,
            zone="workshop",
            event_time=ev.timestamp,
            infra_items=infra_non_op,
        )

    assert len(op_alerts) == 1
    op_alert = op_alerts[0]
    assert op_alert.type == "NON_FUNCTIONAL_EQUIPMENT"
    assert op_alert.item == "lathe"
    assert "lathe" in op_alert.message
    assert "Heuristic indication" in op_alert.message


# --- 4. Audit Log API Tests ---

def test_audit_log_creation_and_query(client, db_session):
    # Create an alert to review
    centre = Centre(id="centre_test_aud", name="Audit Centre", state="MH", district="Pune", lat=18.5, lng=73.8)
    db_session.add(centre)
    alert = Alert(centre_id="centre_test_aud", type="INFRASTRUCTURE_GAP", severity="HIGH", message="Test Deficit", status="open")
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # Patch review
    patch_res = client.patch(
        f"/alerts/{alert.id}",
        json={
            "status": "verified",
            "officer_name": "Dr. V. Rao, Joint Director",
            "review_notes": "Deficit confirmed on site inspection.",
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "verified"

    # Query alert audit trail
    trail_res = client.get(f"/alerts/{alert.id}/audit-trail")
    assert trail_res.status_code == 200
    trail_data = trail_res.json()
    assert len(trail_data) == 1
    assert trail_data[0]["officer_name"] == "Dr. V. Rao, Joint Director"
    assert trail_data[0]["action"] == "VERIFIED"

    # Query global audit logs
    all_logs_res = client.get("/audit-logs?action=VERIFIED")
    assert all_logs_res.status_code == 200
    assert len(all_logs_res.json()) >= 1


# --- 5. Ministry Reports Export Tests ---

def test_ministry_reports_csv_and_pdf(client, db_session):
    # Ensure sample centre exists
    centre = Centre(id="centre_test_rep", name="Report Centre", state="Karnataka", district="Bengaluru", lat=12.9, lng=77.5)
    db_session.add(centre)
    db_session.commit()

    # CSV Export
    csv_res = client.get("/reports/csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    csv_text = csv_res.text
    assert "PRATYAKSHA" in csv_text
    assert "DATA PRIVACY COMPLIANCE NOTICE" in csv_text
    assert "DPDP Act 2023" in csv_text

    # PDF Export
    pdf_res = client.get("/reports/pdf")
    assert pdf_res.status_code == 200
    assert "application/pdf" in pdf_res.headers["content-type"]
    assert pdf_res.content.startswith(b"%PDF")
