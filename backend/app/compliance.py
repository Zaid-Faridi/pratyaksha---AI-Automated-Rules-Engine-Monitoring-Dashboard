"""
Compliance Checks Evaluator for Pratyaksha.
Implements automated, privacy-preserving checks across vocational training trades:
1. Instructor / Trainer Presence (Anonymous spatial presence in demonstration zone)
2. Aggregate PPE Compliance (Helmets, gloves, aprons, eye-protection per zone)
3. Safety Items Verification (Fire extinguisher, first-aid box)
4. Mandatory Signage & Attendance Device Visibility
5. Workstation / Seating Capacity vs Batch Size
6. Zone Activity State (Active, Idle, Empty)

STRICT PRIVACY GUARANTEE:
All checks operate strictly on macroscopic numerical counts and bounding box geometry.
Never attributes PPE or activity to named/identifiable individuals. Zero facial recognition.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def evaluate_instructor_presence(
    person_detections: List[Any],
    instructor_zone_polygon: Optional[np.ndarray] = None,
    frame_shape: Optional[Tuple[int, int]] = None,
) -> Dict[str, Any]:
    """
    Check if an instructor/trainer is present in the designated podium or front demo area.
    If an explicit instructor_zone_polygon is not provided, defaults to the front 25% area
    closest to the blackboard/presentation plane.
    """
    if not person_detections:
        return {
            "instructor_present": False,
            "detected_count_in_podium": 0,
            "heuristic": "zero_persons_in_scene",
        }

    count_in_podium = 0
    for p in person_detections:
        foot_pt = getattr(p, "foot_point", None)
        center_pt = getattr(p, "center_point", None)
        pt = foot_pt if foot_pt is not None else center_pt

        if pt is None:
            continue

        if instructor_zone_polygon is not None and len(instructor_zone_polygon) >= 3:
            # Point in polygon check
            dist = cv2_point_polygon_test(instructor_zone_polygon, pt)
            if dist >= 0:
                count_in_podium += 1
        elif frame_shape is not None:
            # Fallback heuristic: top or front 25% of room height (demonstration dais)
            h, w = frame_shape[:2]
            if pt[1] < (0.35 * h) and (0.15 * w) < pt[0] < (0.85 * w):
                count_in_podium += 1
        else:
            # General fallback if no geometry provided
            count_in_podium = 1 if len(person_detections) >= 1 else 0

    return {
        "instructor_present": bool(count_in_podium >= 1),
        "detected_count_in_podium": count_in_podium,
        "heuristic": "anonymous_spatial_podium_occupancy",
    }


def evaluate_ppe_compliance(
    person_count: int,
    detected_ppe_items: List[Dict[str, Any]],
    required_ppe_specs: List[Dict[str, Any]],
    min_threshold_ratio: float = 0.75,
) -> Dict[str, Any]:
    """
    Compute aggregate PPE compliance for the zone.
    Does NOT match PPE to specific people (zero person crops or tracking).
    Formula: compliance_ratio = detected_relevant_items / (len(required_ppe) * person_count).
    """
    if person_count <= 0 or not required_ppe_specs:
        return {
            "required_specs": required_ppe_specs,
            "compliance_pct": 100.0,
            "is_compliant": True,
            "total_trainees": person_count,
            "wearing_estimate": person_count,
            "detected_items_breakdown": {},
        }

    # Count detected items per required PPE category
    detected_counts: Dict[str, int] = {}
    for item in detected_ppe_items:
        name = item.get("name") or item.get("item", "")
        count = item.get("count", 1)
        detected_counts[name] = detected_counts.get(name, 0) + count

    # Calculate required equipment totals
    total_required_units = 0
    total_detected_units = 0
    breakdown: Dict[str, Any] = {}

    for spec in required_ppe_specs:
        spec_name = spec.get("name", "")
        is_req = spec.get("required", True)
        if not is_req:
            continue

        det_c = detected_counts.get(spec_name, 0)
        # Cap detected items at total people in room to avoid over-counting spares
        effective_c = min(det_c, person_count)
        breakdown[spec_name] = {
            "detected": det_c,
            "effective_worn": effective_c,
            "required": person_count,
        }
        total_required_units += person_count
        total_detected_units += effective_c

    if total_required_units == 0:
        compliance_pct = 100.0
    else:
        compliance_pct = round((total_detected_units / float(total_required_units)) * 100.0, 1)

    is_compliant = (compliance_pct >= (min_threshold_ratio * 100.0))

    return {
        "required_specs": required_ppe_specs,
        "compliance_pct": compliance_pct,
        "is_compliant": is_compliant,
        "total_trainees": person_count,
        "wearing_estimate": min(person_count, int(total_detected_units / max(1, len(required_ppe_specs)))),
        "detected_items_breakdown": breakdown,
        "threshold_pct": round(min_threshold_ratio * 100.0, 1),
    }


def evaluate_safety_items(
    detected_infrastructure: List[Dict[str, Any]],
    mandatory_safety_list: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Check if required emergency and safety items (fire extinguisher, first aid kit) are detected.
    """
    if mandatory_safety_list is None:
        mandatory_safety_list = ["fire_extinguisher", "first_aid_box"]

    detected_names = set()
    for item in detected_infrastructure:
        name = item.get("item", "").lower()
        det_count = item.get("detected", 0)
        if det_count > 0:
            detected_names.add(name)

    missing: List[str] = []
    present: List[str] = []
    for req in mandatory_safety_list:
        if any(req in name or name in req for name in detected_names):
            present.append(req)
        else:
            missing.append(req)

    return {
        "all_present": len(missing) == 0,
        "present_items": present,
        "missing_items": missing,
        "required_items": mandatory_safety_list,
    }


def evaluate_mandatory_signage(
    detected_infrastructure: List[Dict[str, Any]],
    mandatory_signage_list: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Check visibility of scheme banners and biometric attendance terminals.
    """
    if mandatory_signage_list is None:
        mandatory_signage_list = ["safety_signage", "biometric_device"]

    detected_names = set()
    for item in detected_infrastructure:
        name = item.get("item", "").lower()
        if item.get("detected", 0) > 0:
            detected_names.add(name)

    missing: List[str] = []
    present: List[str] = []
    for sign in mandatory_signage_list:
        if any(sign in name or name in sign for name in detected_names):
            present.append(sign)
        else:
            missing.append(sign)

    return {
        "all_visible": len(missing) == 0,
        "visible_signage": present,
        "missing_signage": missing,
    }


def evaluate_workstation_capacity(
    available_functional_workstations: int,
    batch_size: int,
    capacity_ratio: float = 1.0,
    tolerance: float = 0.90,
) -> Dict[str, Any]:
    """
    Verify if functional workstations / seating can support the claimed batch size.
    """
    required_stations = int(np.ceil(batch_size * capacity_ratio))
    is_adequate = (available_functional_workstations >= int(required_stations * tolerance))
    deficit = max(0, required_stations - available_functional_workstations)

    return {
        "is_adequate": is_adequate,
        "available_workstations": available_functional_workstations,
        "batch_size": batch_size,
        "required_stations": required_stations,
        "station_deficit": deficit,
    }


def evaluate_activity_state(
    person_count: int,
    active_equipment_count: int,
    motion_score: float = 0.25,
) -> Dict[str, Any]:
    """
    Classify zone activity into 'active', 'idle', or 'empty'.
    - 'empty': No people present.
    - 'active': People present AND either machines active or motion detected.
    - 'idle': People present for extended windows but zero active machines and low motion.
    """
    if person_count <= 0:
        return {
            "state": "empty",
            "active_trainees": 0,
            "motion_score": 0.0,
            "description": "Zone unoccupied",
        }

    # If trainees are present: check activity signals
    if active_equipment_count > 0 or motion_score >= 0.15:
        return {
            "state": "active",
            "active_trainees": person_count,
            "active_equipment": active_equipment_count,
            "motion_score": motion_score,
            "description": "Engaged practical learning or active instruction",
        }
    else:
        return {
            "state": "idle",
            "active_trainees": person_count,
            "active_equipment": 0,
            "motion_score": motion_score,
            "description": "Trainees present with zero active equipment or practical activity",
        }


def cv2_point_polygon_test(polygon: np.ndarray, point: Tuple[int, int]) -> float:
    """Helper point-in-polygon test without mandatory heavy cv2 import if numpy array."""
    try:
        import cv2
        poly = np.array(polygon, dtype=np.int32)
        return float(cv2.pointPolygonTest(poly, (float(point[0]), float(point[1])), False))
    except Exception:
        # Simple bounding box fallback
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        if min(xs) <= point[0] <= max(xs) and min(ys) <= point[1] <= max(ys):
            return 1.0
        return -1.0
