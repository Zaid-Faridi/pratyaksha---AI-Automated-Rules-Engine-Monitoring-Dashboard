#!/usr/bin/env python3
"""
Setup Demo Footage and Manifest for Multi-Trade, Multi-Centre Support.
Creates:
- demo_footage/<centre_id>/<camera_id>.mp4 for all 6 centres with CCTV visual stamps
- demo_footage/manifest.yaml and demo_footage/manifest.json
"""

import os
import json
import yaml
from pathlib import Path
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
DEMO_DIR = ROOT_DIR / "demo_footage"
SAMPLE_VIDEO = ROOT_DIR / "sample_data" / "skilling_center_demo.mp4"

MANIFEST = {
    "version": "2.0",
    "updated_at": "2026-10-19T11:30:00Z",
    "description": "Master mapping of vocational skilling centres, cameras, trade profiles, zones, and demo violation scenarios.",
    "centres": {
        "centre_mh_01": {
            "centre_id": "centre_mh_01",
            "name": "Pune Skill Development Institute",
            "state": "Maharashtra",
            "district": "Pune",
            "trade_id": "it_lab",
            "trade_name": "IT / Computer Lab",
            "scheme": "PMKVY 4.0",
            "claimed_attendance": 15,
            "active_batch": "Python & Web Development Level 4",
            "cameras": [
                {
                    "camera_id": "cam_01",
                    "name": "Classroom & Workstation View",
                    "video_file": "demo_footage/centre_mh_01/cam_01.mp4",
                    "zones": {
                        "classroom": {
                            "type": "workstation",
                            "polygon": [[40, 40], [620, 40], [620, 680], [40, 680]],
                            "expected_infrastructure": {"computer": 15, "chair": 15},
                        },
                        "instructor_podium": {
                            "type": "instructor",
                            "polygon": [[660, 40], [1240, 40], [1240, 280], [660, 280]],
                            "expected_infrastructure": {"workbench": 1, "chair": 1},
                        },
                        "safety_entrance": {
                            "type": "entrance",
                            "polygon": [[660, 300], [1240, 300], [1240, 680], [660, 680]],
                            "expected_infrastructure": {"fire_extinguisher": 1, "first_aid_box": 1, "biometric_device": 1},
                        },
                    },
                    "sanctioned_inventory": {
                        "computer": 15,
                        "chair": 15,
                        "fire_extinguisher": 1,
                        "first_aid_box": 1,
                        "biometric_device": 1,
                    },
                    "default_scenario": "compliant",
                    "scenarios": {
                        "compliant": {"label": "Compliant Session", "description": "Normal batch operation, 15 present, verified IT terminals and instructor present."},
                        "inflated_attendance": {"label": "Inflated Attendance Claim", "description": "Portal claims 25 trainees; video detects only 8 present (attendance mismatch alert).", "claimed_attendance": 25},
                        "missing_machine": {"label": "Missing Equipment Deficit", "description": "Multiple student desktop workstations missing from lab bench.", "hide_equipment": ["computer"]},
                        "instructor_absent": {"label": "Instructor Absent", "description": "Demonstration podium unoccupied during mandatory teaching window.", "force_instructor_absent": True},
                        "poor_quality": {"label": "Poor Quality / Occlusion", "description": "Simulated camera lens dust, severe blur or occlusion triggering quality gate.", "simulate_blur": True},
                        "idle_session": {"label": "Zone Idle / Inactive", "description": "Students physically seated but prolonged inactivity with zero PC interactions.", "force_idle": True},
                    },
                }
            ],
        },
        "centre_up_02": {
            "centre_id": "centre_up_02",
            "name": "Varanasi Technical Training Academy",
            "state": "Uttar Pradesh",
            "district": "Varanasi",
            "trade_id": "sewing",
            "trade_name": "Sewing & Apparel Making",
            "scheme": "DDU-GKY",
            "claimed_attendance": 20,
            "active_batch": "Self-Employed Tailor Level 3",
            "cameras": [
                {
                    "camera_id": "cam_up_01",
                    "name": "Stitching Line & Cutting Area",
                    "video_file": "demo_footage/centre_up_02/cam_up_01.mp4",
                    "zones": {
                        "stitching_line": {
                            "type": "workstation",
                            "polygon": [[50, 50], [650, 50], [650, 680], [50, 680]],
                            "expected_infrastructure": {"sewing_machine": 12, "chair": 12},
                        },
                        "instructor_podium": {
                            "type": "instructor",
                            "polygon": [[680, 50], [1220, 50], [1220, 260], [680, 260]],
                            "expected_infrastructure": {"cutting_table": 1},
                        },
                        "cutting_zone": {
                            "type": "safety",
                            "polygon": [[680, 280], [1220, 280], [1220, 680], [680, 680]],
                            "expected_infrastructure": {"fire_extinguisher": 1, "first_aid_box": 1},
                        },
                    },
                    "sanctioned_inventory": {
                        "sewing_machine": 12,
                        "chair": 12,
                        "cutting_table": 2,
                        "fire_extinguisher": 1,
                        "first_aid_box": 1,
                    },
                    "default_scenario": "inflated_attendance",
                    "scenarios": {
                        "compliant": {"label": "Compliant Tailoring Batch", "description": "Full attendance, all 12 lockstitch sewing machines operating."},
                        "inflated_attendance": {"label": "Ghost Attendance (Claimed 25 vs 8)", "description": "Claimed 25 registered trainees but only 8 trainees observed on line.", "claimed_attendance": 25},
                        "missing_machine": {"label": "Missing Sewing Machine", "description": "4 Sanctioned industrial sewing machines missing from stitching line.", "hide_equipment": ["sewing_machine"]},
                        "missing_ppe": {"label": "Missing Hairnets & Finger Guards", "description": "Trainees operating apparel machines without protective hairnets/aprons.", "force_missing_ppe": True},
                        "poor_quality": {"label": "Poor Camera Feed", "description": "Sensor noise and high compression artifacts.", "simulate_blur": True},
                    },
                }
            ],
        },
        "centre_ka_03": {
            "centre_id": "centre_ka_03",
            "name": "Bengaluru Digital Skills Centre",
            "state": "Karnataka",
            "district": "Bengaluru Urban",
            "trade_id": "electrical",
            "trade_name": "Electrical & Electronics",
            "scheme": "PMKVY 4.0",
            "claimed_attendance": 16,
            "active_batch": "Field Technician - Wireman Level 4",
            "cameras": [
                {
                    "camera_id": "cam_ka_01",
                    "name": "Wiring Workstations & Testing Bench",
                    "video_file": "demo_footage/centre_ka_03/cam_ka_01.mp4",
                    "zones": {
                        "workstations": {
                            "type": "workstation",
                            "polygon": [[40, 40], [640, 40], [640, 680], [40, 680]],
                            "expected_infrastructure": {"multimeter_bench": 8, "chair": 16},
                        },
                        "instructor_podium": {
                            "type": "instructor",
                            "polygon": [[660, 40], [1240, 40], [1240, 260], [660, 260]],
                            "expected_infrastructure": {"workbench": 1},
                        },
                        "testing_bench": {
                            "type": "safety",
                            "polygon": [[660, 280], [1240, 280], [1240, 680], [660, 680]],
                            "expected_infrastructure": {"fire_extinguisher": 1, "first_aid_box": 1},
                        },
                    },
                    "sanctioned_inventory": {
                        "multimeter_bench": 8,
                        "soldering_station": 8,
                        "chair": 16,
                        "fire_extinguisher": 1,
                        "first_aid_box": 1,
                    },
                    "default_scenario": "missing_machine",
                    "scenarios": {
                        "compliant": {"label": "Compliant Electrical Lab", "description": "All workbenches active with insulated safety tools in place."},
                        "missing_machine": {"label": "Safety Equipment Missing", "description": "Mandatory CO2 fire extinguisher removed from high-voltage testing bench.", "hide_equipment": ["fire_extinguisher"]},
                        "missing_ppe": {"label": "Missing Insulated Gloves", "description": "Live wire testing conducted without 1000V rated dielectric safety gloves.", "force_missing_ppe": True},
                        "capacity_deficit": {"label": "Capacity Deficit", "description": "Batch of 22 students enrolled with only 8 electrical test stations.", "claimed_attendance": 22},
                        "poor_quality": {"label": "CCTV Glare & Low Light", "description": "Severe lighting glare obscuring wiring panels.", "simulate_blur": True},
                    },
                }
            ],
        },
        "centre_or_04": {
            "centre_id": "centre_or_04",
            "name": "Bhubaneswar Vocational Training Centre",
            "state": "Odisha",
            "district": "Khordha",
            "trade_id": "welding",
            "trade_name": "Welding & Fabrication",
            "scheme": "STRIVE",
            "claimed_attendance": 12,
            "active_batch": "Manual Metal Arc Welder Level 3",
            "cameras": [
                {
                    "camera_id": "cam_or_01",
                    "name": "Welding Bay 1 & Grinding Area",
                    "video_file": "demo_footage/centre_or_04/cam_or_01.mp4",
                    "zones": {
                        "welding_bays": {
                            "type": "workstation",
                            "polygon": [[40, 40], [620, 40], [620, 680], [40, 680]],
                            "expected_infrastructure": {"welding_machine": 6, "workbench": 6},
                        },
                        "instructor_podium": {
                            "type": "instructor",
                            "polygon": [[660, 40], [1240, 40], [1240, 260], [660, 260]],
                            "expected_infrastructure": {"workbench": 1},
                        },
                        "grinding_area": {
                            "type": "safety",
                            "polygon": [[660, 280], [1240, 280], [1240, 680], [660, 680]],
                            "expected_infrastructure": {"fire_extinguisher": 1, "first_aid_box": 1},
                        },
                    },
                    "sanctioned_inventory": {
                        "welding_machine": 6,
                        "angle_grinder": 4,
                        "workbench": 6,
                        "fire_extinguisher": 1,
                        "first_aid_box": 1,
                    },
                    "default_scenario": "missing_ppe",
                    "scenarios": {
                        "compliant": {"label": "Fully Compliant Hot Work", "description": "All welders wearing auto-darkening helmets, leather aprons and gloves."},
                        "missing_ppe": {"label": "Severe PPE Violation", "description": "Trainees operating arc welders without helmets or protective gloves (35% compliance).", "force_missing_ppe": True},
                        "instructor_absent": {"label": "Instructor Absent from Bay", "description": "Hazardous hot work conducted without qualified master trainer supervision.", "force_instructor_absent": True},
                        "inflated_attendance": {"label": "Attendance Under-reporting", "description": "Claimed 18 welders vs 5 observed in bays.", "claimed_attendance": 18},
                        "poor_quality": {"label": "Arc Smoke & Lens Fogging", "description": "Heavy welding fumes obscuring bay camera.", "simulate_blur": True},
                    },
                }
            ],
        },
        "centre_rj_05": {
            "centre_id": "centre_rj_05",
            "name": "Jaipur Industrial Skilling Hub",
            "state": "Rajasthan",
            "district": "Jaipur",
            "trade_id": "beauty_wellness",
            "trade_name": "Beauty & Wellness",
            "scheme": "CRAFTSMEN_TRAINING",
            "claimed_attendance": 14,
            "active_batch": "Assistant Beauty Therapist Level 3",
            "cameras": [
                {
                    "camera_id": "cam_rj_01",
                    "name": "Styling Stations & Practice Bay",
                    "video_file": "demo_footage/centre_rj_05/cam_rj_01.mp4",
                    "zones": {
                        "styling_stations": {
                            "type": "workstation",
                            "polygon": [[40, 40], [620, 40], [620, 680], [40, 680]],
                            "expected_infrastructure": {"styling_chair": 6, "mirror_unit": 6},
                        },
                        "instructor_podium": {
                            "type": "instructor",
                            "polygon": [[660, 40], [1240, 40], [1240, 260], [660, 260]],
                            "expected_infrastructure": {"facial_bed": 1},
                        },
                        "reception": {
                            "type": "entrance",
                            "polygon": [[660, 280], [1240, 280], [1240, 680], [660, 680]],
                            "expected_infrastructure": {"first_aid_box": 1, "biometric_device": 1},
                        },
                    },
                    "sanctioned_inventory": {
                        "styling_chair": 6,
                        "mirror_unit": 6,
                        "facial_bed": 2,
                        "first_aid_box": 1,
                        "biometric_device": 1,
                    },
                    "default_scenario": "capacity_deficit",
                    "scenarios": {
                        "compliant": {"label": "Compliant Salon Session", "description": "Trainees practicing on salon chairs with aprons and sanitation kits."},
                        "capacity_deficit": {"label": "Capacity Deficit", "description": "18 trainees assigned to salon with only 6 styling stations (deficit alert).", "claimed_attendance": 18},
                        "missing_machine": {"label": "Missing Sterilizer Unit", "description": "Mandatory UV tool sterilizer cabinet missing from styling bay.", "hide_equipment": ["sterilizer_cabinet"]},
                        "instructor_absent": {"label": "Trainer Absent", "description": "Senior aesthetician absent during practical chemical peel demonstration.", "force_instructor_absent": True},
                        "poor_quality": {"label": "Camera Blur", "description": "Focus ring displaced resulting in unsharp video.", "simulate_blur": True},
                    },
                }
            ],
        },
        "centre_dl_06": {
            "centre_id": "centre_dl_06",
            "name": "Delhi National Capital Training Centre",
            "state": "Delhi",
            "district": "South Delhi",
            "trade_id": "retail",
            "trade_name": "Retail Operations",
            "scheme": "PMKVY 4.0",
            "claimed_attendance": 16,
            "active_batch": "Retail Sales Associate Level 4",
            "cameras": [
                {
                    "camera_id": "cam_dl_01",
                    "name": "Checkout Counters & Display Aisles",
                    "video_file": "demo_footage/centre_dl_06/cam_dl_01.mp4",
                    "zones": {
                        "checkout_zone": {
                            "type": "workstation",
                            "polygon": [[40, 40], [620, 40], [620, 680], [40, 680]],
                            "expected_infrastructure": {"pos_terminal": 4, "barcode_scanner": 4},
                        },
                        "instructor_podium": {
                            "type": "instructor",
                            "polygon": [[660, 40], [1240, 40], [1240, 260], [660, 260]],
                            "expected_infrastructure": {"workbench": 1},
                        },
                        "display_aisles": {
                            "type": "safety",
                            "polygon": [[660, 280], [1240, 280], [1240, 680], [660, 680]],
                            "expected_infrastructure": {"fire_extinguisher": 1, "first_aid_box": 1},
                        },
                    },
                    "sanctioned_inventory": {
                        "pos_terminal": 4,
                        "barcode_scanner": 4,
                        "retail_display_rack": 4,
                        "fire_extinguisher": 1,
                        "first_aid_box": 1,
                    },
                    "default_scenario": "instructor_absent",
                    "scenarios": {
                        "compliant": {"label": "Compliant Retail Mock-Up", "description": "POS checkout lanes operating with retail trainer supervising."},
                        "instructor_absent": {"label": "Trainer Absent During Simulation", "description": "Retail floor running without instructor present at demonstration dais.", "force_instructor_absent": True},
                        "inflated_attendance": {"label": "Attendance Under-reporting", "description": "Claimed 24 trainees vs 7 detected on floor.", "claimed_attendance": 24},
                        "idle_session": {"label": "Floor Inactive", "description": "Cash registers unmanned and zero customer interaction simulation.", "force_idle": True},
                        "poor_quality": {"label": "Store Lighting Malfunction", "description": "Dim aisle illumination causing low contrast.", "simulate_blur": True},
                    },
                }
            ],
        },
    },
}


def create_centre_video(centre_id: str, camera_id: str, trade_name: str, centre_name: str):
    """Generate a clean 720p demo clip with authentic CCTV header stamp."""
    centre_folder = DEMO_DIR / centre_id
    centre_folder.mkdir(parents=True, exist_ok=True)
    target_mp4 = centre_folder / f"{camera_id}.mp4"

    cap = cv2.VideoCapture(str(SAMPLE_VIDEO))
    if not cap.isOpened():
        print(f"[ERROR] Could not open sample video {SAMPLE_VIDEO}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    out = cv2.VideoWriter(str(target_mp4), fourcc, fps, (width, height))

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        # Subtle bottom-left CCTV badge indicating centre, cam, and trade
        stamp_text = f"CCTV [{centre_id.upper()}] {camera_id.upper()} | {trade_name} | {centre_name[:26]}"
        cv2.rectangle(frame, (10, height - 36), (620, height - 10), (10, 10, 10), -1)
        cv2.putText(
            frame,
            stamp_text,
            (16, height - 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 240, 160),
            1,
            cv2.LINE_AA,
        )

        out.write(frame)
        frame_idx += 1

    cap.release()
    out.release()
    print(f"[OK] Generated {target_mp4} ({frame_idx} frames)")


def main():
    print("[INFO] Writing demo footage manifest...")
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    yaml_path = DEMO_DIR / "manifest.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(MANIFEST, f, sort_keys=False, default_flow_style=False)
    print(f"[OK] Wrote {yaml_path}")

    json_path = DEMO_DIR / "manifest.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(MANIFEST, f, indent=2)
    print(f"[OK] Wrote {json_path}")

    print("[INFO] Generating per-centre demo footage clips...")
    for c_id, c_data in MANIFEST["centres"].items():
        trade_name = c_data["trade_name"]
        c_name = c_data["name"]
        for cam in c_data["cameras"]:
            cam_id = cam["camera_id"]
            create_centre_video(c_id, cam_id, trade_name, c_name)

    print("[SUCCESS] Demo footage and manifests prepared!")


if __name__ == "__main__":
    main()
