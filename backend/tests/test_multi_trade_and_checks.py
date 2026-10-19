"""
Comprehensive Unit and Integration Tests for Multi-Trade Support,
Zone-Level Overrides, 6 New Aggregate Compliance Rules, and Demo Footage Manifest.
"""

from datetime import datetime, timedelta
import os
from pathlib import Path
import pytest
import yaml

from app.compliance import (
    evaluate_instructor_presence,
    evaluate_ppe_compliance,
    evaluate_safety_items,
    evaluate_mandatory_signage,
    evaluate_workstation_capacity,
    evaluate_activity_state,
)
from app.models import Alert, Batch, Camera, Centre, DetectionEvent, TradeProfile
from app.rules_engine import RulesEngine
from app.routers.trades import load_seed_trade_profiles, sync_trade_profiles_from_yaml


# ============================================================================
# 1. TRADE PROFILE LOADING & SCHEMA TESTS
# ============================================================================

def test_trade_profiles_yaml_exists_and_contains_seeded_trades():
    """Verify trade_profiles.yaml exists and defines at least 5 required trades."""
    profiles = load_seed_trade_profiles()
    assert len(profiles) >= 5, "Expected at least 5 trade profiles defined in YAML"
    
    expected_trades = ["welding", "sewing", "it_lab", "electrical", "beauty_wellness"]
    for trade_key in expected_trades:
        assert trade_key in profiles, f"Expected '{trade_key}' to be seeded in trade_profiles.yaml"
        tp = profiles[trade_key]
        assert "name" in tp
        assert "sanctioned_equipment" in tp
        assert len(tp["sanctioned_equipment"]) > 0
        assert "required_ppe" in tp
        assert "compliance_checks" in tp
        
        # Verify equipment format
        for eq in tp["sanctioned_equipment"]:
            assert "item" in eq
            assert "expected_per_batch" in eq or "expected_per_zone" in eq
            assert "detector_prompts" in eq or "detector_prompt" in eq
            assert "operability" in eq or "operability_heuristic" in eq


def test_sync_trade_profiles_to_db(db_session):
    """Test synchronizing YAML trade profiles into database."""
    sync_trade_profiles_from_yaml(db_session)
    count = db_session.query(TradeProfile).count()
    assert count >= 5
    
    welding = db_session.query(TradeProfile).filter(TradeProfile.id == "welding").first()
    assert welding is not None
    assert "Welding" in welding.name
    assert any("welding_helmet" in str(ppe) for ppe in welding.required_ppe)


def test_trade_profile_api_endpoints(client, db_session):
    """Test trade profiles CRUD REST endpoints."""
    # List trades
    res = client.get("/trades")
    assert res.status_code == 200
    trades = res.json()
    assert len(trades) >= 5

    # Get specific trade
    res = client.get("/trades/it_lab")
    assert res.status_code == 200
    it_data = res.json()
    assert it_data["id"] == "it_lab"
    assert "computer" in [eq["item"] for eq in it_data["sanctioned_equipment"]]

    # Create new custom trade
    custom_trade = {
        "id": "agriculture_drone",
        "name": "Precision Agriculture & Drone Operations",
        "category": "Agriculture Skill Council",
        "description": "Smart farming and drone piloting standards",
        "sanctioned_equipment": [
            {
                "item": "drone",
                "expected_per_zone": 2,
                "operability_heuristic": "rotor_spin",
                "detector_prompt": "hexacopter agricultural drone",
                "description": "Multi-rotor spray drone",
            }
        ],
        "required_ppe": ["safety_goggles", "hi_vis_vest"],
        "safety_items": ["fire_extinguisher", "first_aid_box"],
        "mandatory_signage": ["safety_signage", "biometric_device"],
        "workstation_capacity_rule": {"min_stations_per_candidate": 1.0},
        "compliance_checks": {"ppe_compliance": {"enabled": True, "min_compliance_ratio": 0.8}},
    }
    create_res = client.post("/trades", json=custom_trade)
    assert create_res.status_code == 201
    assert create_res.json()["id"] == "agriculture_drone"


# ============================================================================
# 2. CENTRE TRADE LINKING & ZONE-LEVEL OVERRIDES TESTS
# ============================================================================

def test_centre_effective_trade_profile_resolution(client, db_session):
    """Test resolving a centre's effective trade standards with zone overrides."""
    sync_trade_profiles_from_yaml(db_session)
    
    # Create centre linked to welding
    centre = Centre(
        id="centre_test_weld",
        name="Test Welding Centre",
        state="Odisha",
        district="Bhubaneswar",
        lat=20.2961,
        lng=85.8245,
        trade_id="welding",
        trade_overrides={
            "sanctioned_equipment": [
                {
                    "item": "welding_machine",
                    "expected_per_zone": 12,  # Overridden from baseline
                    "operability_heuristic": "arc_flash_led",
                    "detector_prompt": "industrial arc welding machine unit",
                }
            ],
            "required_ppe": ["welding_helmet", "heavy_leather_gloves", "leather_apron"],
        },
    )
    db_session.add(centre)
    db_session.commit()

    # Query effective profile
    res = client.get("/trades/centres/centre_test_weld/effective")
    assert res.status_code == 200
    eff = res.json()
    assert eff["trade_id"] == "welding"
    # Overridden equipment count
    assert eff["sanctioned_equipment"][0]["expected_per_zone"] == 12
    assert "heavy_leather_gloves" in eff["required_ppe"]


def test_update_centre_trade_overrides_endpoint(client, db_session):
    """Test updating a centre's trade and overrides via PUT endpoint."""
    sync_trade_profiles_from_yaml(db_session)
    centre = Centre(
        id="centre_test_put",
        name="Test Dynamic Centre",
        state="Karnataka",
        district="Bengaluru",
        lat=12.9716,
        lng=77.5946,
        trade_id="it_lab",
    )
    db_session.add(centre)
    db_session.commit()

    # Switch trade to electrical with custom overrides
    payload = {
        "trade_id": "electrical",
        "trade_overrides": {
            "required_ppe": ["insulated_safety_gloves"],
        },
    }
    put_res = client.put("/trades/centres/centre_test_put/effective", json=payload)
    assert put_res.status_code == 200
    assert put_res.json()["trade_id"] == "electrical"

    # Verify updated effective profile
    get_res = client.get("/trades/centres/centre_test_put/effective")
    assert get_res.json()["trade_id"] == "electrical"
    assert get_res.json()["required_ppe"] == ["insulated_safety_gloves"]


# ============================================================================
# 3. SIX AGGREGATE COMPLIANCE CHECKS TESTS
# ============================================================================

class DummyDetection:
    """Mock detection object for testing geometric occupancy."""
    def __init__(self, center_point, foot_point=None):
        self.center_point = center_point
        self.foot_point = foot_point or center_point


def test_evaluate_instructor_presence():
    """Verify anonymous instructor zone presence evaluation."""
    # Case A: Person in front podium area (y < 0.35 * h)
    detections_present = [DummyDetection(center_point=(500, 100))]
    res_a = evaluate_instructor_presence(
        person_detections=detections_present,
        frame_shape=(720, 1280),
    )
    assert res_a["instructor_present"] is True
    assert res_a["detected_count_in_podium"] >= 1

    # Case B: Persons only in back seating area (y > 0.5 * h)
    detections_back = [DummyDetection(center_point=(500, 600))]
    res_b = evaluate_instructor_presence(
        person_detections=detections_back,
        frame_shape=(720, 1280),
    )
    assert res_b["instructor_present"] is False
    assert res_b["detected_count_in_podium"] == 0

    # Case C: Empty room
    res_c = evaluate_instructor_presence(person_detections=[])
    assert res_c["instructor_present"] is False


def test_evaluate_ppe_compliance():
    """Verify aggregate PPE compliance ratio calculation without person attribution."""
    required_specs = [
        {"name": "welding_helmet", "required": True},
        {"name": "leather_apron", "required": True},
    ]

    # Case A: 10 persons, 10 helmets and 10 aprons detected (100% compliant)
    detected_items_compliant = [
        {"name": "welding_helmet", "count": 10},
        {"name": "leather_apron", "count": 10},
    ]
    res_a = evaluate_ppe_compliance(
        person_count=10,
        detected_ppe_items=detected_items_compliant,
        required_ppe_specs=required_specs,
        min_threshold_ratio=0.8,
    )
    assert res_a["is_compliant"] is True
    assert res_a["compliance_pct"] == 100.0

    # Case B: 10 persons, only 3 helmets detected (15% compliance < 80% threshold)
    detected_items_deficit = [
        {"name": "welding_helmet", "count": 3},
        {"name": "leather_apron", "count": 0},
    ]
    res_b = evaluate_ppe_compliance(
        person_count=10,
        detected_ppe_items=detected_items_deficit,
        required_ppe_specs=required_specs,
        min_threshold_ratio=0.8,
    )
    assert res_b["is_compliant"] is False
    assert res_b["compliance_pct"] < 80.0


def test_evaluate_safety_items():
    """Verify fire extinguisher and first aid box presence checks."""
    mandatory = ["fire_extinguisher", "first_aid_box"]
    
    # Case A: Both present
    infra_ok = [
        {"item": "fire_extinguisher", "detected": 1},
        {"item": "first_aid_box", "detected": 1},
    ]
    res_ok = evaluate_safety_items(infra_ok, mandatory)
    assert res_ok["all_present"] is True
    assert len(res_ok["missing_items"]) == 0

    # Case B: Fire extinguisher missing
    infra_missing = [
        {"item": "fire_extinguisher", "detected": 0},
        {"item": "first_aid_box", "detected": 1},
    ]
    res_missing = evaluate_safety_items(infra_missing, mandatory)
    assert res_missing["all_present"] is False
    assert "fire_extinguisher" in res_missing["missing_items"]


def test_evaluate_mandatory_signage():
    """Verify entrance banner and attendance device visibility."""
    mandatory = ["safety_signage", "biometric_device"]

    # Case A: Both present
    infra_ok = [
        {"item": "safety_signage", "detected": 1},
        {"item": "biometric_device", "detected": 1},
    ]
    res_ok = evaluate_mandatory_signage(infra_ok, mandatory)
    assert res_ok["all_visible"] is True

    # Case B: Signage missing
    infra_missing = [
        {"item": "safety_signage", "detected": 0},
        {"item": "biometric_device", "detected": 1},
    ]
    res_missing = evaluate_mandatory_signage(infra_missing, mandatory)
    assert res_missing["all_visible"] is False
    assert "safety_signage" in res_missing["missing_signage"]


def test_evaluate_workstation_capacity():
    """Verify workstation capacity vs batch size."""
    # 15 stations for 12 batch candidates (adequate)
    res_ok = evaluate_workstation_capacity(
        available_functional_workstations=15,
        batch_size=12,
        capacity_ratio=1.0,
    )
    assert res_ok["is_adequate"] is True
    assert res_ok["station_deficit"] == 0

    # 6 stations for 15 batch candidates (deficit of 9)
    res_deficit = evaluate_workstation_capacity(
        available_functional_workstations=6,
        batch_size=15,
        capacity_ratio=1.0,
    )
    assert res_deficit["is_adequate"] is False
    assert res_deficit["station_deficit"] == 9


def test_evaluate_activity_state():
    """Verify zone activity classification (active, idle, empty)."""
    # Case A: Active practical session
    res_active = evaluate_activity_state(
        person_count=10,
        active_equipment_count=6,
        motion_score=0.45,
    )
    assert res_active["state"] == "active"

    # Case B: Idle classroom (people present, zero active tools, low motion)
    res_idle = evaluate_activity_state(
        person_count=10,
        active_equipment_count=0,
        motion_score=0.05,
    )
    assert res_idle["state"] == "idle"

    # Case C: Empty room
    res_empty = evaluate_activity_state(
        person_count=0,
        active_equipment_count=0,
        motion_score=0.0,
    )
    assert res_empty["state"] == "empty"


# ============================================================================
# 4. RULES ENGINE COMPLIANCE DISPATCH & DE-DUPLICATION
# ============================================================================

def test_evaluate_trade_compliance_checks_integration(db_session):
    """Test full rules engine integration with trade checks and de-duplication."""
    sync_trade_profiles_from_yaml(db_session)
    centre = Centre(
        id="centre_rule_test",
        name="Rules Engine Test Centre",
        state="Maharashtra",
        district="Pune",
        lat=18.5204,
        lng=73.8567,
        trade_id="welding",
    )
    cam = Camera(
        id="cam_rule_01",
        centre_id="centre_rule_test",
        status="online",
        zone_names=["workshop"],
    )
    # Active batch for today (covering full day 00:00 - 23:59)
    days_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    batch = Batch(
        id="batch_weld_01",
        centre_id="centre_rule_test",
        name="Arc Welding Morning",
        start_time="00:00",
        end_time="23:59",
        days=days_list,
        zone="workshop",
    )
    db_session.add(centre)
    db_session.add(cam)
    db_session.add(batch)
    db_session.commit()

    now = datetime.utcnow()

    # Event 1: Instructor absent, sample 1 of 3
    ev1 = DetectionEvent(
        camera_id="cam_rule_01",
        timestamp=now - timedelta(seconds=60),
        zone="workshop",
        person_count_raw=10,
        person_count_smoothed=10,
        compliance_metrics={"instructor_present": False, "ppe_aggregate_compliance": 0.4},
    )
    db_session.add(ev1)
    db_session.commit()

    alerts_1 = RulesEngine.evaluate_trade_compliance_checks(
        db=db_session,
        centre_id="centre_rule_test",
        camera=cam,
        zone="workshop",
        event_time=now - timedelta(seconds=60),
        current_event=ev1,
    )
    # Consecutive threshold is 3, so should not fire on sample 1
    assert len([a for a in alerts_1 if a.type == "INSTRUCTOR_ABSENT"]) == 0

    # Event 2: Second consecutive violation triggers INSTRUCTOR_ABSENT alert (k=2 consecutive windows)
    ev2 = DetectionEvent(
        camera_id="cam_rule_01",
        timestamp=now - timedelta(seconds=30),
        zone="workshop",
        person_count_raw=10,
        person_count_smoothed=10,
        compliance_metrics={"instructor_present": False, "ppe_aggregate_compliance": 0.4},
    )
    db_session.add(ev2)
    db_session.commit()
    alerts_2 = RulesEngine.evaluate_trade_compliance_checks(
        db=db_session,
        centre_id="centre_rule_test",
        camera=cam,
        zone="workshop",
        event_time=now - timedelta(seconds=30),
        current_event=ev2,
    )
    inst_alerts_2 = [a for a in alerts_2 if a.type == "INSTRUCTOR_ABSENT"]
    assert len(inst_alerts_2) == 1
    assert inst_alerts_2[0].severity in ["HIGH", "CRITICAL"]

    # Event 3: Third consecutive event while previous alert is open -> De-duplication suppresses duplicate
    ev3 = DetectionEvent(
        camera_id="cam_rule_01",
        timestamp=now,
        zone="workshop",
        person_count_raw=10,
        person_count_smoothed=10,
        compliance_metrics={"instructor_present": False, "ppe_aggregate_compliance": 0.4},
    )
    db_session.add(ev3)
    db_session.commit()
    alerts_3 = RulesEngine.evaluate_trade_compliance_checks(
        db=db_session,
        centre_id="centre_rule_test",
        camera=cam,
        zone="workshop",
        event_time=now,
        current_event=ev3,
    )
    assert len([a for a in alerts_3 if a.type == "INSTRUCTOR_ABSENT"]) == 0


# ============================================================================
# 5. PER-CENTRE FOOTAGE MANIFEST TESTS
# ============================================================================

def test_demo_footage_manifest_integrity():
    """Verify demo_footage manifest exists and accurately maps all 6 centres."""
    manifest_path = Path("demo_footage/manifest.yaml")
    if not manifest_path.exists():
        manifest_path = Path("demo_footage/manifest.json")
    assert manifest_path.exists(), "demo_footage/manifest.yaml or manifest.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f) if manifest_path.suffix in [".yaml", ".yml"] else __import__("json").load(f)

    centres = manifest.get("centres", {})
    assert len(centres) >= 5, "Manifest must configure at least 5 skilling centres"

    for c_id, c_data in centres.items():
        assert "trade_id" in c_data
        assert "cameras" in c_data
        assert len(c_data["cameras"]) > 0
        for cam in c_data["cameras"]:
            assert "video_file" in cam
            assert "zones" in cam
            assert "demo_scenarios" in cam or "active_batch" in c_data
