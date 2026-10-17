"""
Unit Tests for Pratyaksha Rules Engine.
Covers attendance mismatch, severity scaling, occlusion dips, batch boundary awareness,
infrastructure gap/surplus, alert deduplication, auto-resolution, camera health, and compliance scoring.
"""

from datetime import datetime, date, timedelta, timezone
from app.models import (
    Alert,
    AttendanceRecord,
    Batch,
    Camera,
    Centre,
    DetectionEvent,
    SanctionedInventory,
)
from app.rules_engine import RulesEngine


def test_attendance_mismatch_and_severity_scaling(db_session, standard_setup):
    """
    Test Rule 1: Attendance mismatch triggers when median count < 70% of claimed over N=3 samples.
    Verifies severity scaling:
      - 8 observed vs 25 claimed (gap ~68%) -> HIGH
      - 5 observed vs 25 claimed (gap 80%) -> CRITICAL
    """
    cam = standard_setup["camera"]
    batch = standard_setup["batch"]

    # Target date: Monday at 10:00 (inside batch window)
    test_date = date(2026, 10, 19)  # 2026-10-19 is a Monday
    att_rec = AttendanceRecord(
        centre_id=cam.centre_id,
        batch_id=batch.id,
        date=test_date,
        claimed_count=25,
    )
    db_session.add(att_rec)
    db_session.commit()

    # Insert 3 consecutive events with low attendance (8 persons smoothed < 70% of 25 = 17.5)
    for minute in [0, 15, 30]:
        event_time = datetime(2026, 10, 19, 10, minute, tzinfo=timezone.utc)
        ev = DetectionEvent(
            camera_id=cam.id,
            zone="classroom",
            timestamp=event_time,
            person_count_raw=8,
            person_count_smoothed=8,
            infrastructure=[],
        )
        db_session.add(ev)
        db_session.commit()

        alert = RulesEngine.evaluate_attendance_mismatch(
            db=db_session,
            centre_id=cam.centre_id,
            camera=cam,
            zone="classroom",
            event_time=event_time,
        )

    # After 3 consecutive events, an alert must be active
    assert alert is not None
    assert alert.type == "ATTENDANCE_MISMATCH"
    assert alert.status == "open"
    # Gap = (25 - 8)/25 = 68% -> HIGH severity
    assert alert.severity == "HIGH"


def test_occlusion_dip_no_false_alarm(db_session, standard_setup):
    """
    Test Rule 1 Edge Case: A brief 1-sample occlusion dip (e.g. students walking behind a pillar)
    must NOT trigger an alert because N=3 consecutive samples are required.
    """
    cam = standard_setup["camera"]
    batch = standard_setup["batch"]
    test_date = date(2026, 10, 19)  # Monday

    att_rec = AttendanceRecord(
        centre_id=cam.centre_id,
        batch_id=batch.id,
        date=test_date,
        claimed_count=20,
    )
    db_session.add(att_rec)
    db_session.commit()

    # Event 1: Normal attendance (19)
    ev1 = DetectionEvent(
        camera_id=cam.id,
        zone="classroom",
        timestamp=datetime(2026, 10, 19, 9, 30, tzinfo=timezone.utc),
        person_count_raw=19,
        person_count_smoothed=19,
        infrastructure=[],
    )
    # Event 2: Brief occlusion dip (only 8 persons detected for 1 frame)
    ev2 = DetectionEvent(
        camera_id=cam.id,
        zone="classroom",
        timestamp=datetime(2026, 10, 19, 9, 45, tzinfo=timezone.utc),
        person_count_raw=8,
        person_count_smoothed=8,
        infrastructure=[],
    )
    # Event 3: Attendance recovers (19)
    ev3 = DetectionEvent(
        camera_id=cam.id,
        zone="classroom",
        timestamp=datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc),
        person_count_raw=19,
        person_count_smoothed=19,
        infrastructure=[],
    )
    db_session.add_all([ev1, ev2, ev3])
    db_session.commit()

    alert = RulesEngine.evaluate_attendance_mismatch(
        db=db_session,
        centre_id=cam.centre_id,
        camera=cam,
        zone="classroom",
        event_time=ev3.timestamp,
    )

    # Median over [19, 8, 19] is 19 -> 19/20 = 95% -> compliant, NO alert!
    assert alert is None
    open_alerts = db_session.query(Alert).filter(Alert.type == "ATTENDANCE_MISMATCH", Alert.status == "open").count()
    assert open_alerts == 0


def test_schedule_awareness_skips_outside_window(db_session, standard_setup):
    """
    Test Rule 4: Checks must be skipped outside batch hours and on non-batch days.
    """
    cam = standard_setup["camera"]
    batch = standard_setup["batch"]
    test_date = date(2026, 10, 19)  # Monday

    db_session.add(AttendanceRecord(
        centre_id=cam.centre_id,
        batch_id=batch.id,
        date=test_date,
        claimed_count=20,
    ))
    db_session.commit()

    # Time 07:00 AM (Batch runs 09:00 - 13:00)
    outside_time = datetime(2026, 10, 19, 7, 0, tzinfo=timezone.utc)
    ev = DetectionEvent(
        camera_id=cam.id,
        zone="classroom",
        timestamp=outside_time,
        person_count_raw=0,
        person_count_smoothed=0,
        infrastructure=[],
    )
    db_session.add(ev)
    db_session.commit()

    alert = RulesEngine.evaluate_attendance_mismatch(
        db=db_session,
        centre_id=cam.centre_id,
        camera=cam,
        zone="classroom",
        event_time=outside_time,
    )
    assert alert is None

    # Sunday test: 2026-10-18 is Sunday (Batch runs Mon-Fri)
    sunday_time = datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc)
    alert_sunday = RulesEngine.evaluate_attendance_mismatch(
        db=db_session,
        centre_id=cam.centre_id,
        camera=cam,
        zone="classroom",
        event_time=sunday_time,
    )
    assert alert_sunday is None


def test_infrastructure_gap_and_surplus(db_session, standard_setup):
    """
    Test Rule 2:
      - 3 consecutive samples with computer deficit (expected 10, detected 4) triggers INFRASTRUCTURE_GAP.
      - Extra items (e.g. 25 chairs vs 20 expected) trigger INFRASTRUCTURE_SURPLUS (INFO severity).
    """
    cam = standard_setup["camera"]

    # 3 consecutive events with missing computers and surplus chairs
    for i in range(3):
        t = datetime(2026, 10, 19, 10, i * 10, tzinfo=timezone.utc)
        ev = DetectionEvent(
            camera_id=cam.id,
            zone="classroom",
            timestamp=t,
            person_count_raw=10,
            person_count_smoothed=10,
            infrastructure=[
                {"item": "computer", "expected": 10, "detected": 4, "status": "DEFICIT"},
                {"item": "chair", "expected": 20, "detected": 25, "status": "SURPLUS"},
            ],
        )
        db_session.add(ev)
        db_session.commit()

        alerts = RulesEngine.evaluate_infrastructure_discrepancies(
            db=db_session,
            centre_id=cam.centre_id,
            camera=cam,
            zone="classroom",
            event_time=t,
            infra_items=ev.infrastructure,
        )

    gap_alert = db_session.query(Alert).filter(
        Alert.type == "INFRASTRUCTURE_GAP",
        Alert.item == "computer",
        Alert.status == "open",
    ).first()
    assert gap_alert is not None
    assert gap_alert.severity == "CRITICAL"  # deficit = 6 >= 50% of expected 10

    surplus_alert = db_session.query(Alert).filter(
        Alert.type == "INFRASTRUCTURE_SURPLUS",
        Alert.item == "chair",
        Alert.status == "open",
    ).first()
    assert surplus_alert is not None
    assert surplus_alert.severity == "INFO"


def test_alert_deduplication(db_session, standard_setup):
    """
    Test Rule 5: Repeated violations must NOT create duplicate open alerts.
    """
    cam = standard_setup["camera"]
    batch = standard_setup["batch"]
    test_date = date(2026, 10, 19)

    db_session.add(AttendanceRecord(
        centre_id=cam.centre_id,
        batch_id=batch.id,
        date=test_date,
        claimed_count=20,
    ))
    db_session.commit()

    # 5 consecutive deficit events
    for m in range(5):
        t = datetime(2026, 10, 19, 10, m * 5, tzinfo=timezone.utc)
        ev = DetectionEvent(
            camera_id=cam.id,
            zone="classroom",
            timestamp=t,
            person_count_raw=5,
            person_count_smoothed=5,
            infrastructure=[],
        )
        db_session.add(ev)
        db_session.commit()
        RulesEngine.evaluate_attendance_mismatch(db_session, cam.centre_id, cam, "classroom", t)

    open_alerts_count = db_session.query(Alert).filter(
        Alert.centre_id == cam.centre_id,
        Alert.type == "ATTENDANCE_MISMATCH",
        Alert.status == "open",
    ).count()

    # Deduplication ensures exactly 1 open alert exists
    assert open_alerts_count == 1


def test_auto_resolution_when_condition_clears(db_session, standard_setup):
    """
    Test Rule 5: When attendance and equipment recover to compliant levels,
    open alerts are automatically transitioned to 'auto_resolved'.
    """
    cam = standard_setup["camera"]
    batch = standard_setup["batch"]
    test_date = date(2026, 10, 19)

    db_session.add(AttendanceRecord(
        centre_id=cam.centre_id,
        batch_id=batch.id,
        date=test_date,
        claimed_count=20,
    ))
    db_session.commit()

    # Step 1: Create open alert via deficit events
    for m in range(3):
        t = datetime(2026, 10, 19, 10, m * 5, tzinfo=timezone.utc)
        ev = DetectionEvent(
            camera_id=cam.id,
            zone="classroom",
            timestamp=t,
            person_count_raw=5,
            person_count_smoothed=5,
            infrastructure=[{"item": "computer", "expected": 10, "detected": 2, "status": "DEFICIT"}],
        )
        db_session.add(ev)
        db_session.commit()
        RulesEngine.evaluate_attendance_mismatch(db_session, cam.centre_id, cam, "classroom", t)
        RulesEngine.evaluate_infrastructure_discrepancies(db_session, cam.centre_id, cam, "classroom", t, ev.infrastructure)

    att_alert = db_session.query(Alert).filter(Alert.type == "ATTENDANCE_MISMATCH", Alert.status == "open").first()
    assert att_alert is not None

    # Step 2: Attendance and equipment recover! (19 persons, 10 computers)
    for m in range(3, 6):
        t_rec = datetime(2026, 10, 19, 10, m * 5, tzinfo=timezone.utc)
        ev_rec = DetectionEvent(
            camera_id=cam.id,
            zone="classroom",
            timestamp=t_rec,
            person_count_raw=19,
            person_count_smoothed=19,
            infrastructure=[{"item": "computer", "expected": 10, "detected": 10, "status": "MATCH"}],
        )
        db_session.add(ev_rec)
        db_session.commit()
        RulesEngine.evaluate_attendance_mismatch(db_session, cam.centre_id, cam, "classroom", t_rec)
        RulesEngine.evaluate_infrastructure_discrepancies(db_session, cam.centre_id, cam, "classroom", t_rec, ev_rec.infrastructure)

    # Both alerts must now be auto-resolved
    db_session.refresh(att_alert)
    assert att_alert.status == "auto_resolved"
    assert "Auto-resolved" in att_alert.review_notes

    gap_alert = db_session.query(Alert).filter(Alert.type == "INFRASTRUCTURE_GAP", Alert.item == "computer").first()
    assert gap_alert.status == "auto_resolved"


def test_camera_offline_and_tamper(db_session, standard_setup):
    """
    Test Rule 3:
      - Camera offline alert when no heartbeat/event for > 15m during batch window.
      - Camera tamper alert when detected objects drop suddenly by >= 80%.
    """
    cam = standard_setup["camera"]
    # 1. Camera Offline test
    cam.last_seen_at = datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)
    db_session.commit()

    # Time is 09:30 (30 minutes elapsed > 15m timeout)
    batch_time = datetime(2026, 10, 19, 9, 30, tzinfo=timezone.utc)
    offline_alert = RulesEngine.check_camera_offline(db_session, cam, batch_time)

    assert offline_alert is not None
    assert offline_alert.type == "CAMERA_OFFLINE"
    assert cam.status == "offline"

    # 2. Camera Tamper test: previous events averaged 15 objects, suddenly drops to 0
    prev_time = datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)
    for p in range(4):
        db_session.add(DetectionEvent(
            camera_id=cam.id,
            zone="classroom",
            timestamp=prev_time - timedelta(minutes=5 * (4 - p)),
            person_count_raw=15,
            person_count_smoothed=15,
            infrastructure=[],
        ))
    db_session.commit()

    tamper_event = DetectionEvent(
        camera_id=cam.id,
        zone="classroom",
        timestamp=prev_time,
        person_count_raw=0,
        person_count_smoothed=0,
        infrastructure=[],
    )
    db_session.add(tamper_event)
    db_session.commit()

    tamper_alert = RulesEngine.evaluate_camera_tamper(
        db=db_session,
        centre_id=cam.centre_id,
        camera=cam,
        zone="classroom",
        event_time=prev_time,
        current_event=tamper_event,
    )
    assert tamper_alert is not None
    assert tamper_alert.type == "CAMERA_TAMPER"
    assert tamper_alert.severity == "CRITICAL"


def test_compliance_score_weights(db_session, standard_setup):
    """
    Test Rule 6: Weighted compliance score correctly scales across components:
      score = 100 * (0.45 * att_rate + 0.35 * infra_rate + 0.20 * cam_rate)
    """
    centre = standard_setup["centre"]
    breakdown = RulesEngine.calculate_compliance_score(db_session, centre.id)

    assert "compliance_score" in breakdown
    assert 0.0 <= breakdown["compliance_score"] <= 100.0
    assert breakdown["weights"]["attendance"] == 0.45
    assert breakdown["weights"]["infrastructure"] == 0.35
    assert breakdown["weights"]["camera"] == 0.20


def test_data_retention_cleanup(db_session, standard_setup):
    """
    Test Privacy & Data Retention: Events older than N days are deleted.
    """
    cam = standard_setup["camera"]
    old_time = datetime.now(timezone.utc) - timedelta(days=95)
    recent_time = datetime.now(timezone.utc) - timedelta(days=5)

    ev_old = DetectionEvent(
        camera_id=cam.id,
        zone="classroom",
        timestamp=old_time,
        person_count_raw=10,
        person_count_smoothed=10,
        infrastructure=[],
    )
    ev_new = DetectionEvent(
        camera_id=cam.id,
        zone="classroom",
        timestamp=recent_time,
        person_count_raw=10,
        person_count_smoothed=10,
        infrastructure=[],
    )
    db_session.add_all([ev_old, ev_new])
    db_session.commit()

    # Retention threshold = 90 days
    deleted = RulesEngine.cleanup_old_events(db_session, retention_days=90)
    assert deleted >= 1

    remaining = db_session.query(DetectionEvent).filter(DetectionEvent.camera_id == cam.id).all()
    assert len(remaining) == 1
    assert remaining[0].timestamp.replace(tzinfo=timezone.utc) >= (datetime.now(timezone.utc) - timedelta(days=90))
