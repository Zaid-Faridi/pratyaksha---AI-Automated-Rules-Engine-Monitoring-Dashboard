#!/usr/bin/env python3
"""
Database Seed Script for Pratyaksha Backend with Multi-Trade & Multi-Centre Support.
Creates:
- 6 Standard Vocational Trade Profiles (Welding, Sewing, IT Lab, Electrical, Beauty & Wellness, Retail)
- 6 Skilling Centres mapped to trades across Indian states
- Real cameras, multi-zone configurations, and sanctioned equipment baselines
- Training batches with operational schedules
- Claimed attendance records
- Seeded detection events with rich compliance metrics demonstrating key violations:
    1. Pune (IT Lab): High compliance benchmark (attendance, equipment, instructor present)
    2. Varanasi (Sewing): Attendance shortfall (claimed 25 vs 8 observed)
    3. Bengaluru (Electrical): Missing safety equipment & equipment deficit (fire extinguisher missing)
    4. Bhubaneswar (Welding): Severe PPE violation (35% compliance, missing helmets/gloves) & camera offline
    5. Jaipur (Beauty & Wellness): Capacity deficit & missing scheme signage
    6. Delhi (Retail): Instructor absent from demonstration area during active batch
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
    TradeProfile,
    utcnow,
)
from app.rules_engine import RulesEngine
from app.routers.trades import sync_trade_profiles_from_yaml


def seed():
    print("[INFO] Initializing clean database tables...")
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()

    try:
        print("[INFO] Seeding 6 vocational trade profiles from trade_profiles.yaml...")
        sync_trade_profiles_from_yaml(db)
        tp_count = db.query(TradeProfile).count()
        print(f"       Loaded {tp_count} trade profiles.")

        print("[INFO] Creating 6 multi-trade sample skilling centres...")
        centres_data = [
            Centre(
                id="centre_mh_01",
                name="Pune Skill Development Institute",
                state="Maharashtra",
                district="Pune",
                lat=18.5204,
                lng=73.8567,
                scheme="PMKVY 4.0",
                trade_id="it_lab",
            ),
            Centre(
                id="centre_up_02",
                name="Varanasi Technical Training Academy",
                state="Uttar Pradesh",
                district="Varanasi",
                lat=25.3176,
                lng=82.9739,
                scheme="DDU-GKY",
                trade_id="sewing",
            ),
            Centre(
                id="centre_ka_03",
                name="Bengaluru Digital Skills Centre",
                state="Karnataka",
                district="Bengaluru Urban",
                lat=12.9716,
                lng=77.5946,
                scheme="PMKVY 4.0",
                trade_id="electrical",
            ),
            Centre(
                id="centre_or_04",
                name="Bhubaneswar Vocational Training Centre",
                state="Odisha",
                district="Khordha",
                lat=20.2961,
                lng=85.8245,
                scheme="STRIVE",
                trade_id="welding",
            ),
            Centre(
                id="centre_rj_05",
                name="Jaipur Industrial Skilling Hub",
                state="Rajasthan",
                district="Jaipur",
                lat=26.9124,
                lng=75.7873,
                scheme="CRAFTSMEN_TRAINING",
                trade_id="beauty_wellness",
            ),
            Centre(
                id="centre_dl_06",
                name="Delhi National Capital Training Centre",
                state="Delhi",
                district="South Delhi",
                lat=28.6139,
                lng=77.2090,
                scheme="PMKVY 4.0",
                trade_id="retail",
            ),
        ]
        db.add_all(centres_data)
        db.commit()

        print("[INFO] Adding cameras and multi-zone configurations...")
        cameras_data = [
            Camera(
                id="cam_01",
                centre_id="centre_mh_01",
                zone_names=["classroom", "computer_lab", "instructor_podium"],
                status="online",
                rtsp_url="demo_footage/centre_mh_01/cam_01.mp4",
            ),
            Camera(
                id="cam_mh_01",
                centre_id="centre_mh_01",
                zone_names=["classroom", "computer_lab"],
                status="online",
                rtsp_url="demo_footage/centre_mh_01/cam_01.mp4",
            ),
            Camera(
                id="cam_up_01",
                centre_id="centre_up_02",
                zone_names=["cutting_zone", "stitching_line"],
                status="online",
                rtsp_url="demo_footage/centre_up_02/cam_up_01.mp4",
            ),
            Camera(
                id="cam_ka_01",
                centre_id="centre_ka_03",
                zone_names=["workstations", "testing_bench"],
                status="online",
                rtsp_url="demo_footage/centre_ka_03/cam_ka_01.mp4",
            ),
            Camera(
                id="cam_or_01",
                centre_id="centre_or_04",
                zone_names=["welding_bays", "grinding_area"],
                status="offline",
                rtsp_url="demo_footage/centre_or_04/cam_or_01.mp4",
            ),
            Camera(
                id="cam_rj_01",
                centre_id="centre_rj_05",
                zone_names=["styling_stations", "reception"],
                status="online",
                rtsp_url="demo_footage/centre_rj_05/cam_rj_01.mp4",
            ),
            Camera(
                id="cam_dl_01",
                centre_id="centre_dl_06",
                zone_names=["checkout_zone", "display_aisles"],
                status="online",
                rtsp_url="demo_footage/centre_dl_06/cam_dl_01.mp4",
            ),
        ]
        db.add_all(cameras_data)
        db.commit()

        print("[INFO] Setting up sanctioned trade infrastructure baselines...")
        inventory_data = [
            # Pune (IT Lab: Compliant)
            SanctionedInventory(centre_id="centre_mh_01", zone="computer_lab", item="computer", expected_count=15),
            SanctionedInventory(centre_id="centre_mh_01", zone="computer_lab", item="chair", expected_count=15),
            SanctionedInventory(centre_id="centre_mh_01", zone="computer_lab", item="fire_extinguisher", expected_count=1),
            SanctionedInventory(centre_id="centre_mh_01", zone="computer_lab", item="first_aid_box", expected_count=1),
            SanctionedInventory(centre_id="centre_mh_01", zone="computer_lab", item="safety_signage", expected_count=1),

            # Varanasi (Sewing & Apparel)
            SanctionedInventory(centre_id="centre_up_02", zone="stitching_line", item="sewing_machine", expected_count=12),
            SanctionedInventory(centre_id="centre_up_02", zone="stitching_line", item="cutting_table", expected_count=2),
            SanctionedInventory(centre_id="centre_up_02", zone="stitching_line", item="chair", expected_count=12),
            SanctionedInventory(centre_id="centre_up_02", zone="stitching_line", item="fire_extinguisher", expected_count=1),
            SanctionedInventory(centre_id="centre_up_02", zone="stitching_line", item="first_aid_box", expected_count=1),

            # Bengaluru (Electrical & Electronics: Missing fire extinguisher)
            SanctionedInventory(centre_id="centre_ka_03", zone="workstations", item="multimeter_bench", expected_count=8),
            SanctionedInventory(centre_id="centre_ka_03", zone="workstations", item="soldering_station", expected_count=8),
            SanctionedInventory(centre_id="centre_ka_03", zone="workstations", item="chair", expected_count=16),
            SanctionedInventory(centre_id="centre_ka_03", zone="workstations", item="fire_extinguisher", expected_count=1),
            SanctionedInventory(centre_id="centre_ka_03", zone="workstations", item="first_aid_box", expected_count=1),

            # Bhubaneswar (Welding & Fabrication)
            SanctionedInventory(centre_id="centre_or_04", zone="welding_bays", item="welding_machine", expected_count=6),
            SanctionedInventory(centre_id="centre_or_04", zone="welding_bays", item="angle_grinder", expected_count=4),
            SanctionedInventory(centre_id="centre_or_04", zone="welding_bays", item="workbench", expected_count=6),
            SanctionedInventory(centre_id="centre_or_04", zone="welding_bays", item="fire_extinguisher", expected_count=2),
            SanctionedInventory(centre_id="centre_or_04", zone="welding_bays", item="first_aid_box", expected_count=1),

            # Jaipur (Beauty & Wellness: Capacity shortfall)
            SanctionedInventory(centre_id="centre_rj_05", zone="styling_stations", item="styling_chair", expected_count=8),
            SanctionedInventory(centre_id="centre_rj_05", zone="styling_stations", item="mirror_station", expected_count=8),
            SanctionedInventory(centre_id="centre_rj_05", zone="styling_stations", item="facial_steamer", expected_count=4),
            SanctionedInventory(centre_id="centre_rj_05", zone="styling_stations", item="fire_extinguisher", expected_count=1),
            SanctionedInventory(centre_id="centre_rj_05", zone="styling_stations", item="safety_signage", expected_count=1),

            # Delhi (Retail Assistant)
            SanctionedInventory(centre_id="centre_dl_06", zone="checkout_zone", item="pos_terminal", expected_count=3),
            SanctionedInventory(centre_id="centre_dl_06", zone="checkout_zone", item="billing_counter", expected_count=3),
            SanctionedInventory(centre_id="centre_dl_06", zone="checkout_zone", item="display_rack", expected_count=6),
            SanctionedInventory(centre_id="centre_dl_06", zone="checkout_zone", item="fire_extinguisher", expected_count=1),
        ]
        db.add_all(inventory_data)
        db.commit()

        print("[INFO] Configuring training batches...")
        days_all = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        batches_data = [
            Batch(
                id="batch_pune_01",
                centre_id="centre_mh_01",
                name="Cyber Security & Cloud Admin",
                start_time="09:00",
                end_time="13:00",
                days=days_all,
                zone="computer_lab",
            ),
            Batch(
                id="batch_vns_01",
                centre_id="centre_up_02",
                name="Apparel Pattern Maker & Sewing",
                start_time="09:00",
                end_time="13:00",
                days=days_all,
                zone="stitching_line",
            ),
            Batch(
                id="batch_blr_01",
                centre_id="centre_ka_03",
                name="Industrial Electrician & Wireman",
                start_time="10:00",
                end_time="14:00",
                days=days_all,
                zone="workstations",
            ),
            Batch(
                id="batch_bbsr_01",
                centre_id="centre_or_04",
                name="Shielded Metal Arc Welder (SMAW)",
                start_time="09:00",
                end_time="13:00",
                days=days_all,
                zone="welding_bays",
            ),
            Batch(
                id="batch_jpr_01",
                centre_id="centre_rj_05",
                name="Assistant Beauty Therapist",
                start_time="09:00",
                end_time="13:00",
                days=days_all,
                zone="styling_stations",
            ),
            Batch(
                id="batch_dl_01",
                centre_id="centre_dl_06",
                name="Retail Sales & POS Associate",
                start_time="09:00",
                end_time="13:00",
                days=days_all,
                zone="checkout_zone",
            ),
        ]
        db.add_all(batches_data)
        db.commit()

        print("[INFO] Submitting claimed attendance records...")
        base_date = date.today() - timedelta(days=2)
        dates = [base_date + timedelta(days=i) for i in range(3)]

        attendance_data = [
            # Pune: Claimed 15 (Matches observed)
            AttendanceRecord(centre_id="centre_mh_01", batch_id="batch_pune_01", date=d, claimed_count=15)
            for d in dates
        ] + [
            # Varanasi: Claimed 25 (Observed only 8 -> Severe mismatch)
            AttendanceRecord(centre_id="centre_up_02", batch_id="batch_vns_01", date=d, claimed_count=25)
            for d in dates
        ] + [
            # Bengaluru: Claimed 14 (Matches observed 14)
            AttendanceRecord(centre_id="centre_ka_03", batch_id="batch_blr_01", date=d, claimed_count=14)
            for d in dates
        ] + [
            # Bhubaneswar: Claimed 12 (Observed 11 on Day 1, offline days 2 & 3)
            AttendanceRecord(centre_id="centre_or_04", batch_id="batch_bbsr_01", date=d, claimed_count=12)
            for d in dates
        ] + [
            # Jaipur: Claimed 20 (Capacity allows only 8 stations -> Deficit)
            AttendanceRecord(centre_id="centre_rj_05", batch_id="batch_jpr_01", date=d, claimed_count=20)
            for d in dates
        ] + [
            # Delhi: Claimed 16 (Instructor absent)
            AttendanceRecord(centre_id="centre_dl_06", batch_id="batch_dl_01", date=d, claimed_count=16)
            for d in dates
        ]
        db.add_all(attendance_data)
        db.commit()

        print("[INFO] Generating simulated multi-trade detection events...")
        events_to_add = []

        for d in dates:
            sample_hours = [(9, 30), (10, 0), (10, 30), (11, 0), (11, 30), (12, 0)]

            for h, m in sample_hours:
                event_dt = datetime(d.year, d.month, d.day, h, m, 0, tzinfo=timezone.utc)

                # 1. Pune (IT Lab: High Compliance Benchmark)
                events_to_add.append(
                    DetectionEvent(
                        camera_id="cam_01",
                        zone="computer_lab",
                        timestamp=event_dt,
                        person_count_raw=15,
                        person_count_smoothed=15,
                        infrastructure=[
                            {"item": "computer", "expected": 15, "detected": 15, "status": "MATCH", "operability": "operational"},
                            {"item": "chair", "expected": 15, "detected": 15, "status": "MATCH", "operability": "operational"},
                            {"item": "fire_extinguisher", "expected": 1, "detected": 1, "status": "MATCH"},
                            {"item": "first_aid_box", "expected": 1, "detected": 1, "status": "MATCH"},
                            {"item": "safety_signage", "expected": 1, "detected": 1, "status": "MATCH"},
                        ],
                        compliance_metrics={
                            "instructor_present": True,
                            "ppe_compliance": {"compliance_pct": 100.0, "is_compliant": True, "total_trainees": 15},
                            "safety_items": {"all_present": True, "missing_items": []},
                            "signage_and_devices": {"all_visible": True, "missing_signage": []},
                            "capacity_check": {"is_adequate": True, "available_workstations": 15, "batch_size": 15, "station_deficit": 0},
                            "activity_state": "active",
                        },
                        is_reliable=True,
                    )
                )

                # 2. Varanasi (Sewing: Severe attendance shortfall - claimed 25 vs 8 present)
                events_to_add.append(
                    DetectionEvent(
                        camera_id="cam_up_01",
                        zone="stitching_line",
                        timestamp=event_dt,
                        person_count_raw=8,
                        person_count_smoothed=8,
                        infrastructure=[
                            {"item": "sewing_machine", "expected": 12, "detected": 12, "status": "MATCH", "operability": "operational"},
                            {"item": "cutting_table", "expected": 2, "detected": 2, "status": "MATCH", "operability": "operational"},
                            {"item": "chair", "expected": 12, "detected": 12, "status": "MATCH", "operability": "operational"},
                            {"item": "fire_extinguisher", "expected": 1, "detected": 1, "status": "MATCH"},
                            {"item": "first_aid_box", "expected": 1, "detected": 1, "status": "MATCH"},
                        ],
                        compliance_metrics={
                            "instructor_present": True,
                            "ppe_compliance": {"compliance_pct": 80.0, "is_compliant": True, "total_trainees": 8},
                            "safety_items": {"all_present": True, "missing_items": []},
                            "signage_and_devices": {"all_visible": True, "missing_signage": []},
                            "capacity_check": {"is_adequate": True, "available_workstations": 12, "batch_size": 25, "station_deficit": 0},
                            "activity_state": "active",
                        },
                        is_reliable=True,
                    )
                )

                # 3. Bengaluru (Electrical: Missing fire extinguisher & deficit)
                events_to_add.append(
                    DetectionEvent(
                        camera_id="cam_ka_01",
                        zone="workstations",
                        timestamp=event_dt,
                        person_count_raw=14,
                        person_count_smoothed=14,
                        infrastructure=[
                            {"item": "multimeter_bench", "expected": 8, "detected": 5, "status": "DEFICIT", "operability": "operational"},
                            {"item": "soldering_station", "expected": 8, "detected": 5, "status": "DEFICIT", "operability": "operational"},
                            {"item": "chair", "expected": 16, "detected": 16, "status": "MATCH"},
                            {"item": "first_aid_box", "expected": 1, "detected": 1, "status": "MATCH"},
                            # fire_extinguisher intentionally omitted to trigger SAFETY_EQUIPMENT_MISSING
                        ],
                        compliance_metrics={
                            "instructor_present": True,
                            "ppe_compliance": {"compliance_pct": 85.0, "is_compliant": True, "total_trainees": 14},
                            "safety_items": {"all_present": False, "missing_items": ["fire_extinguisher"]},
                            "signage_and_devices": {"all_visible": True, "missing_signage": []},
                            "capacity_check": {"is_adequate": True, "available_workstations": 10, "batch_size": 14, "station_deficit": 0},
                            "activity_state": "active",
                        },
                        is_reliable=True,
                    )
                )

                # 4. Bhubaneswar (Welding: Severe PPE Violation - 35% compliance & unpowered machine)
                if d == dates[0] and (h, m) in sample_hours[:3]:
                    events_to_add.append(
                        DetectionEvent(
                            camera_id="cam_or_01",
                            zone="welding_bays",
                            timestamp=event_dt,
                            person_count_raw=11,
                            person_count_smoothed=11,
                            infrastructure=[
                                {"item": "welding_machine", "expected": 6, "detected": 6, "status": "MATCH", "operability": "non_operational", "signals": {"power_led": False}},
                                {"item": "workbench", "expected": 6, "detected": 6, "status": "MATCH", "operability": "operational"},
                                {"item": "fire_extinguisher", "expected": 2, "detected": 2, "status": "MATCH"},
                                {"item": "first_aid_box", "expected": 1, "detected": 1, "status": "MATCH"},
                            ],
                            compliance_metrics={
                                "instructor_present": True,
                                "ppe_compliance": {
                                    "compliance_pct": 35.0,
                                    "is_compliant": False,
                                    "total_trainees": 11,
                                    "detected_items_breakdown": {
                                        "welding_helmet": {"detected": 3, "required": 11},
                                        "leather_gloves": {"detected": 4, "required": 11},
                                    },
                                },
                                "safety_items": {"all_present": True, "missing_items": []},
                                "signage_and_devices": {"all_visible": True, "missing_signage": []},
                                "capacity_check": {"is_adequate": True, "available_workstations": 6, "batch_size": 12, "station_deficit": 0},
                                "activity_state": "active",
                            },
                            is_reliable=True,
                        )
                    )

                # 5. Jaipur (Beauty: Workstation capacity deficit - 8 stations vs 20 claimed)
                events_to_add.append(
                    DetectionEvent(
                        camera_id="cam_rj_01",
                        zone="styling_stations",
                        timestamp=event_dt,
                        person_count_raw=19,
                        person_count_smoothed=19,
                        infrastructure=[
                            {"item": "styling_chair", "expected": 8, "detected": 8, "status": "MATCH", "operability": "operational"},
                            {"item": "mirror_station", "expected": 8, "detected": 8, "status": "MATCH", "operability": "operational"},
                            {"item": "facial_steamer", "expected": 4, "detected": 4, "status": "MATCH", "operability": "operational"},
                            {"item": "fire_extinguisher", "expected": 1, "detected": 1, "status": "MATCH"},
                            # safety_signage missing
                        ],
                        compliance_metrics={
                            "instructor_present": True,
                            "ppe_compliance": {"compliance_pct": 82.0, "is_compliant": True, "total_trainees": 19},
                            "safety_items": {"all_present": True, "missing_items": []},
                            "signage_and_devices": {"all_visible": False, "missing_signage": ["safety_signage"]},
                            "capacity_check": {
                                "is_adequate": False,
                                "available_workstations": 8,
                                "batch_size": 20,
                                "station_deficit": 12,
                            },
                            "activity_state": "active",
                        },
                        is_reliable=True,
                    )
                )

                # 6. Delhi (Retail: Instructor absent from podium during active batch)
                events_to_add.append(
                    DetectionEvent(
                        camera_id="cam_dl_01",
                        zone="checkout_zone",
                        timestamp=event_dt,
                        person_count_raw=15,
                        person_count_smoothed=15,
                        infrastructure=[
                            {"item": "pos_terminal", "expected": 3, "detected": 3, "status": "MATCH", "operability": "operational"},
                            {"item": "billing_counter", "expected": 3, "detected": 3, "status": "MATCH", "operability": "operational"},
                            {"item": "display_rack", "expected": 6, "detected": 6, "status": "MATCH"},
                            {"item": "fire_extinguisher", "expected": 1, "detected": 1, "status": "MATCH"},
                        ],
                        compliance_metrics={
                            "instructor_present": False,  # Triggers INSTRUCTOR_ABSENT
                            "ppe_compliance": {"compliance_pct": 100.0, "is_compliant": True, "total_trainees": 15},
                            "safety_items": {"all_present": True, "missing_items": []},
                            "signage_and_devices": {"all_visible": True, "missing_signage": []},
                            "capacity_check": {"is_adequate": True, "available_workstations": 3, "batch_size": 16, "station_deficit": 0},
                            "activity_state": "active",
                        },
                        is_reliable=True,
                    )
                )

        db.add_all(events_to_add)
        db.commit()

        # Update camera statuses
        for c_id in ["cam_01", "cam_mh_01", "cam_up_01", "cam_ka_01", "cam_rj_01", "cam_dl_01"]:
            c = db.query(Camera).filter(Camera.id == c_id).first()
            if c:
                c.last_seen_at = utcnow()
                c.status = "online"

        cam_or = db.query(Camera).filter(Camera.id == "cam_or_01").first()
        if cam_or:
            cam_or.last_seen_at = utcnow() - timedelta(days=2)
            cam_or.status = "offline"

        db.commit()

        print("[INFO] Evaluating comprehensive compliance rules across all trades...")
        for ev in events_to_add:
            cam = db.query(Camera).filter(Camera.id == ev.camera_id).first()
            if cam:
                RulesEngine.evaluate_attendance_mismatch(db, cam.centre_id, cam, ev.zone, ev.timestamp)
                RulesEngine.evaluate_infrastructure_discrepancies(db, cam.centre_id, cam, ev.zone, ev.timestamp, ev.infrastructure)
                RulesEngine.evaluate_apparent_operability(db, cam.centre_id, cam, ev.zone, ev.timestamp, ev.infrastructure)
                RulesEngine.evaluate_trade_compliance_checks(db, cam.centre_id, cam, ev.zone, ev.timestamp, ev)

        # Trigger camera offline check for Bhubaneswar
        fake_batch_time = datetime.now(timezone.utc).replace(hour=10, minute=30)
        RulesEngine.check_camera_offline(db, cam_or, fake_batch_time)

        alerts_count = db.query(Alert).count()
        print(f"[SUCCESS] Multi-Trade Database Seeded Successfully!")
        print(f"  • Trade Profiles seeded : {tp_count}")
        print(f"  • Centres configured    : {len(centres_data)}")
        print(f"  • Cameras configured    : {len(cameras_data)}")
        print(f"  • Inventory items       : {len(inventory_data)}")
        print(f"  • Batches scheduled     : {len(batches_data)}")
        print(f"  • Attendance records    : {len(attendance_data)}")
        print(f"  • Detection events      : {len(events_to_add)}")
        print(f"  • Active compliance alerts : {alerts_count}")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
