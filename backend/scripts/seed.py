#!/usr/bin/env python3
"""
Database Seed Script for Pratyaksha Backend.
Creates:
- 5 Skilling Centres across Indian states (Maharashtra, UP, Karnataka, Odisha, Rajasthan)
- Cameras with zone definitions
- Sanctioned inventory baselines
- Training batches with operational schedules
- 3 days of claimed attendance records
- 3 days of simulated detection events with intentional violations:
    1. Varanasi: Severe attendance shortfall (claimed 25 vs observed 8)
    2. Bengaluru: Infrastructure deficit (sanctioned 15 computers vs detected 6)
    3. Bhubaneswar: Camera offline / tamper during batch hours
    4. Pune: High compliance benchmark (attendance & equipment matching)
    5. Jaipur: Moderate compliance with minor equipment surplus
"""

from datetime import datetime, date, time, timedelta, timezone
import random
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal, init_db, engine, Base
from app.models import (
    Centre,
    Camera,
    SanctionedInventory,
    Batch,
    AttendanceRecord,
    DetectionEvent,
    Alert,
    utcnow,
)
from app.rules_engine import RulesEngine


def seed():
    print("[INFO] Initializing clean database tables...")
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()

    try:
        print("[INFO] Creating 5 sample skilling centres...")
        centres_data = [
            Centre(
                id="centre_mh_01",
                name="Pune Skill Development Institute",
                state="Maharashtra",
                district="Pune",
                lat=18.5204,
                lng=73.8567,
                scheme="PMKVY 4.0",
            ),
            Centre(
                id="centre_up_02",
                name="Varanasi Technical Training Academy",
                state="Uttar Pradesh",
                district="Varanasi",
                lat=25.3176,
                lng=82.9739,
                scheme="DDU-GKY",
            ),
            Centre(
                id="centre_ka_03",
                name="Bengaluru Digital Skills Centre",
                state="Karnataka",
                district="Bengaluru Urban",
                lat=12.9716,
                lng=77.5946,
                scheme="PMKVY 4.0",
            ),
            Centre(
                id="centre_or_04",
                name="Bhubaneswar Vocational Training Centre",
                state="Odisha",
                district="Khordha",
                lat=20.2961,
                lng=85.8245,
                scheme="STRIVE",
            ),
            Centre(
                id="centre_rj_05",
                name="Jaipur Industrial Skilling Hub",
                state="Rajasthan",
                district="Jaipur",
                lat=26.9124,
                lng=75.7873,
                scheme="CRAFTSMEN_TRAINING",
            ),
        ]
        db.add_all(centres_data)
        db.commit()

        print("[INFO] Adding cameras and zone configurations...")
        cameras_data = [
            Camera(
                id="cam_01",
                centre_id="centre_mh_01",
                zone_names=["classroom", "workshop"],
                status="online",
                rtsp_url="rtsp://pune-feed.internal/stream1",
            ),
            Camera(
                id="cam_mh_01",
                centre_id="centre_mh_01",
                zone_names=["classroom", "workshop"],
                status="online",
                rtsp_url="rtsp://pune-feed.internal/stream1",
            ),
            Camera(
                id="cam_up_01",
                centre_id="centre_up_02",
                zone_names=["classroom"],
                status="online",
                rtsp_url="rtsp://varanasi-feed.internal/stream1",
            ),
            Camera(
                id="cam_ka_01",
                centre_id="centre_ka_03",
                zone_names=["computer_lab"],
                status="online",
                rtsp_url="rtsp://blr-feed.internal/stream1",
            ),
            Camera(
                id="cam_or_01",
                centre_id="centre_or_04",
                zone_names=["workshop"],
                status="offline",
                rtsp_url="rtsp://bbsr-feed.internal/stream1",
            ),
            Camera(
                id="cam_rj_01",
                centre_id="centre_rj_05",
                zone_names=["classroom"],
                status="online",
                rtsp_url="rtsp://jaipur-feed.internal/stream1",
            ),
        ]
        db.add_all(cameras_data)
        db.commit()

        print("[INFO] Setting up sanctioned infrastructure baselines...")
        inventory_data = [
            # Pune (Compliant)
            SanctionedInventory(centre_id="centre_mh_01", zone="classroom", item="chair", expected_count=20),
            SanctionedInventory(centre_id="centre_mh_01", zone="classroom", item="bench", expected_count=6),
            SanctionedInventory(centre_id="centre_mh_01", zone="classroom", item="computer", expected_count=10),
            # Varanasi (Attendance violation centre)
            SanctionedInventory(centre_id="centre_up_02", zone="classroom", item="chair", expected_count=25),
            SanctionedInventory(centre_id="centre_up_02", zone="classroom", item="bench", expected_count=8),
            # Bengaluru (Equipment Deficit violation centre: expected 15 computers)
            SanctionedInventory(centre_id="centre_ka_03", zone="computer_lab", item="computer", expected_count=15),
            SanctionedInventory(centre_id="centre_ka_03", zone="computer_lab", item="chair", expected_count=15),
            # Bhubaneswar (Camera offline centre)
            SanctionedInventory(centre_id="centre_or_04", zone="workshop", item="workbench", expected_count=6),
            SanctionedInventory(centre_id="centre_or_04", zone="workshop", item="chair", expected_count=12),
            # Jaipur (Slight surplus)
            SanctionedInventory(centre_id="centre_rj_05", zone="classroom", item="chair", expected_count=20),
            SanctionedInventory(centre_id="centre_rj_05", zone="classroom", item="bench", expected_count=6),
        ]
        db.add_all(inventory_data)
        db.commit()

        print("[INFO] Configuring training batches...")
        days_all = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        batches_data = [
            Batch(
                id="batch_pune_01",
                centre_id="centre_mh_01",
                name="Solar Technician Level 4",
                start_time="09:00",
                end_time="13:00",
                days=days_all,
                zone="classroom",
            ),
            Batch(
                id="batch_vns_01",
                centre_id="centre_up_02",
                name="Handloom & Textile Operator",
                start_time="09:00",
                end_time="13:00",
                days=days_all,
                zone="classroom",
            ),
            Batch(
                id="batch_blr_01",
                centre_id="centre_ka_03",
                name="Junior Software Developer",
                start_time="10:00",
                end_time="14:00",
                days=days_all,
                zone="computer_lab",
            ),
            Batch(
                id="batch_bbsr_01",
                centre_id="centre_or_04",
                name="Industrial Welder",
                start_time="09:00",
                end_time="13:00",
                days=days_all,
                zone="workshop",
            ),
            Batch(
                id="batch_jpr_01",
                centre_id="centre_rj_05",
                name="Electrician Assistant",
                start_time="09:00",
                end_time="13:00",
                days=days_all,
                zone="classroom",
            ),
        ]
        db.add_all(batches_data)
        db.commit()

        print("[INFO] Submitting 3 days of claimed attendance records...")
        base_date = date.today() - timedelta(days=2)
        dates = [base_date + timedelta(days=i) for i in range(3)]

        attendance_data = [
            # Pune: Claimed 20
            AttendanceRecord(centre_id="centre_mh_01", batch_id="batch_pune_01", date=d, claimed_count=20)
            for d in dates
        ] + [
            # Varanasi: Claimed 25 (Intentional attendance shortfall)
            AttendanceRecord(centre_id="centre_up_02", batch_id="batch_vns_01", date=d, claimed_count=25)
            for d in dates
        ] + [
            # Bengaluru: Claimed 14
            AttendanceRecord(centre_id="centre_ka_03", batch_id="batch_blr_01", date=d, claimed_count=14)
            for d in dates
        ] + [
            # Bhubaneswar: Claimed 12
            AttendanceRecord(centre_id="centre_or_04", batch_id="batch_bbsr_01", date=d, claimed_count=12)
            for d in dates
        ] + [
            # Jaipur: Claimed 20
            AttendanceRecord(centre_id="centre_rj_05", batch_id="batch_jpr_01", date=d, claimed_count=20)
            for d in dates
        ]
        db.add_all(attendance_data)
        db.commit()

        print("[INFO] Simulating 3 days of detection events across centres...")
        events_to_add = []

        for d in dates:
            # 6 sample times throughout the morning batch window (09:30 to 12:30)
            sample_hours = [(9, 30), (10, 0), (10, 30), (11, 0), (11, 30), (12, 0)]

            for h, m in sample_hours:
                event_dt = datetime(d.year, d.month, d.day, h, m, 0, tzinfo=timezone.utc)

                # 1. Pune: Compliant (19-20 persons, 20 chairs, 6 benches, 10 computers)
                events_to_add.append(
                    DetectionEvent(
                        camera_id="cam_mh_01",
                        zone="classroom",
                        timestamp=event_dt,
                        person_count_raw=19,
                        person_count_smoothed=19,
                        infrastructure=[
                            {"item": "chair", "expected": 20, "detected": 20, "status": "MATCH"},
                            {"item": "bench", "expected": 6, "detected": 6, "status": "MATCH"},
                            {"item": "computer", "expected": 10, "detected": 10, "status": "MATCH"},
                        ],
                    )
                )

                # 2. Varanasi: VIOLATION - Severe attendance mismatch (claimed 25, observed 8)
                events_to_add.append(
                    DetectionEvent(
                        camera_id="cam_up_01",
                        zone="classroom",
                        timestamp=event_dt,
                        person_count_raw=8,
                        person_count_smoothed=8,
                        infrastructure=[
                            {"item": "chair", "expected": 25, "detected": 25, "status": "MATCH"},
                            {"item": "bench", "expected": 8, "detected": 8, "status": "MATCH"},
                        ],
                    )
                )

                # 3. Bengaluru: VIOLATION - Equipment deficit (expected 15 computers, only 6 detected)
                events_to_add.append(
                    DetectionEvent(
                        camera_id="cam_ka_01",
                        zone="computer_lab",
                        timestamp=event_dt,
                        person_count_raw=14,
                        person_count_smoothed=14,
                        infrastructure=[
                            {"item": "computer", "expected": 15, "detected": 6, "status": "DEFICIT"},
                            {"item": "chair", "expected": 15, "detected": 15, "status": "MATCH"},
                        ],
                    )
                )

                # 4. Jaipur: Compliant with minor chair surplus (22 detected vs 20 expected)
                events_to_add.append(
                    DetectionEvent(
                        camera_id="cam_rj_01",
                        zone="classroom",
                        timestamp=event_dt,
                        person_count_raw=19,
                        person_count_smoothed=19,
                        infrastructure=[
                            {"item": "chair", "expected": 20, "detected": 22, "status": "SURPLUS"},
                            {"item": "bench", "expected": 6, "detected": 6, "status": "MATCH"},
                        ],
                    )
                )

                # 5. Bhubaneswar: Only transmit during day 1; days 2 & 3 go offline / tampered
                if d == dates[0] and (h, m) in sample_hours[:3]:
                    events_to_add.append(
                        DetectionEvent(
                            camera_id="cam_or_01",
                            zone="workshop",
                            timestamp=event_dt,
                            person_count_raw=11,
                            person_count_smoothed=11,
                            infrastructure=[
                                {"item": "workbench", "expected": 6, "detected": 6, "status": "MATCH"},
                                {"item": "chair", "expected": 12, "detected": 12, "status": "MATCH"},
                            ],
                        )
                    )

        db.add_all(events_to_add)
        db.commit()

        # Update camera last seen timestamps
        cam_mh = db.query(Camera).filter(Camera.id == "cam_mh_01").first()
        cam_mh.last_seen_at = utcnow()
        cam_mh.status = "online"

        cam_up = db.query(Camera).filter(Camera.id == "cam_up_01").first()
        cam_up.last_seen_at = utcnow()
        cam_up.status = "online"

        cam_ka = db.query(Camera).filter(Camera.id == "cam_ka_01").first()
        cam_ka.last_seen_at = utcnow()
        cam_ka.status = "online"

        cam_rj = db.query(Camera).filter(Camera.id == "cam_rj_01").first()
        cam_rj.last_seen_at = utcnow()
        cam_rj.status = "online"

        # Bhubaneswar camera was last seen 2 days ago
        cam_or = db.query(Camera).filter(Camera.id == "cam_or_01").first()
        cam_or.last_seen_at = utcnow() - timedelta(days=2)
        cam_or.status = "offline"

        db.commit()

        print("[INFO] Evaluating compliance rules to generate audit alerts...")
        # Evaluate rules across seeded data
        for ev in events_to_add:
            cam = db.query(Camera).filter(Camera.id == ev.camera_id).first()
            RulesEngine.evaluate_attendance_mismatch(db, cam.centre_id, cam, ev.zone, ev.timestamp)
            RulesEngine.evaluate_infrastructure_discrepancies(db, cam.centre_id, cam, ev.zone, ev.timestamp, ev.infrastructure)

        # Trigger camera offline check for Bhubaneswar
        fake_batch_time = datetime.now(timezone.utc).replace(hour=10, minute=30)
        RulesEngine.check_camera_offline(db, cam_or, fake_batch_time)

        alerts_count = db.query(Alert).count()
        print(f"[SUCCESS] Database seeded successfully!")
        print(f"  • Centres created      : {len(centres_data)}")
        print(f"  • Cameras configured   : {len(cameras_data)}")
        print(f"  • Inventory items      : {len(inventory_data)}")
        print(f"  • Batches scheduled    : {len(batches_data)}")
        print(f"  • Attendance submitted : {len(attendance_data)}")
        print(f"  • Detection events     : {len(events_to_add)}")
        print(f"  • Compliance alerts    : {alerts_count}")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
