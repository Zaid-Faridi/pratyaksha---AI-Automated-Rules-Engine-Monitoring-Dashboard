"""
Evaluation Metrics Engine for Pratyaksha.
Computes:
1. Detection-level metrics: Person count MAE, RMSE, MPE, and infrastructure Precision, Recall, F1.
2. Decision-level metrics: Full confusion matrix (TP, FP, FN, TN), Precision, Recall, F1, FPR, FNR
   for attendance mismatch alerts and missing equipment alerts.
"""

import math
from typing import Any, Dict, List, Tuple
import cv2
import numpy as np

from detector import ObjectDetector
from zones import Zone


def compute_detection_metrics(
    detector: ObjectDetector,
    ground_truth: List[Dict[str, Any]],
    zones: Dict[str, Zone],
    class_mapping: Dict[str, List[str]],
    imgsz: int = 640,
) -> Dict[str, Any]:
    """
    Evaluate person counting and infrastructure item identification against ground truth.
    """
    def is_item_of_type(detected_cls: str, target: str) -> bool:
        valid = class_mapping.get(target, [target])
        return detected_cls.lower() in [c.lower() for c in valid]

    # Person count accumulators per zone and overall
    person_errors: Dict[str, List[float]] = {"overall": []}
    for z in zones.keys():
        person_errors[z] = []

    # Infrastructure counters: item -> {tp, fp, fn}
    infra_counters: Dict[str, Dict[str, int]] = {
        "chair": {"tp": 0, "fp": 0, "fn": 0},
        "table": {"tp": 0, "fp": 0, "fn": 0},
        "laptop": {"tp": 0, "fp": 0, "fn": 0},
    }

    per_variant_errors: Dict[str, List[float]] = {}

    for entry in ground_truth:
        img_path = entry["image_path"]
        variant = entry.get("variant", "baseline")
        frame = cv2.imread(img_path)
        if frame is None:
            continue

        if variant not in per_variant_errors:
            per_variant_errors[variant] = []

        detections = detector.detect(frame)

        for zone_name, zone in zones.items():
            gt_zone = entry["zones"].get(zone_name, {})
            true_persons = gt_zone.get("persons", 0)

            # 1. Person Count Evaluation
            zone_persons = [
                d for d in detections
                if d.class_name == "person" and zone.contains_point(d.foot_point)
            ]
            pred_persons = len(zone_persons)
            diff = pred_persons - true_persons

            person_errors["overall"].append(diff)
            person_errors[zone_name].append(diff)
            per_variant_errors[variant].append(diff)

            # 2. Infrastructure Detection Evaluation
            for item in infra_counters.keys():
                true_count = gt_zone.get(item, 0)
                matching = [
                    d for d in detections
                    if d.class_name != "person"
                    and is_item_of_type(d.class_name, item)
                    and zone.contains_point(d.center_point)
                ]
                pred_count = len(matching)

                tp = min(pred_count, true_count)
                fp = max(0, pred_count - true_count)
                fn = max(0, true_count - pred_count)

                infra_counters[item]["tp"] += tp
                infra_counters[item]["fp"] += fp
                infra_counters[item]["fn"] += fn

    # Calculate person count metrics
    def summarize_errors(errs: List[float]) -> Dict[str, float]:
        if not errs:
            return {"mae": 0.0, "rmse": 0.0, "mpe": 0.0}
        mae = float(np.mean(np.abs(errs)))
        rmse = float(np.sqrt(np.mean(np.square(errs))))
        # Avoid div by zero by using max(1, true)
        mpe = float(np.mean(np.abs(errs) / 5.0) * 100.0)
        return {"mae": round(mae, 3), "rmse": round(rmse, 3), "mpe": round(mpe, 2)}

    person_metrics = {z: summarize_errors(errs) for z, errs in person_errors.items()}

    # Calculate infrastructure metrics
    infra_metrics = {}
    total_tp = sum(c["tp"] for c in infra_counters.values())
    total_fp = sum(c["fp"] for c in infra_counters.values())
    total_fn = sum(c["fn"] for c in infra_counters.values())

    for item, c in infra_counters.items():
        prec = c["tp"] / (c["tp"] + c["fp"]) if (c["tp"] + c["fp"]) > 0 else 0.0
        rec = c["tp"] / (c["tp"] + c["fn"]) if (c["tp"] + c["fn"]) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        infra_metrics[item] = {
            "precision": round(prec, 3),
            "recall": round(rec, 3),
            "f1": round(f1, 3),
            "tp": c["tp"],
            "fp": c["fp"],
            "fn": c["fn"],
        }

    macro_prec = np.mean([m["precision"] for m in infra_metrics.values()])
    macro_rec = np.mean([m["recall"] for m in infra_metrics.values()])
    macro_f1 = np.mean([m["f1"] for m in infra_metrics.values()])
    infra_metrics["macro_avg"] = {
        "precision": round(float(macro_prec), 3),
        "recall": round(float(macro_rec), 3),
        "f1": round(float(macro_f1), 3),
    }

    variant_summary = {v: summarize_errors(errs) for v, errs in per_variant_errors.items()}

    return {
        "person_metrics": person_metrics,
        "infrastructure_metrics": infra_metrics,
        "variant_breakdown": variant_summary,
        "total_evaluated_frames": len(ground_truth),
    }


def compute_decision_metrics(
    scenarios: List[Dict[str, Any]],
    attendance_threshold_ratio: float = 0.70,
    consecutive_windows: int = 3,
) -> Dict[str, Any]:
    """
    Run the rules engine logic across the scenario manifest and compute confusion matrices.
    """
    # 1. Attendance Mismatch Alert Matrix
    att_matrix = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    # 2. Missing Equipment Alert Matrix
    infra_matrix = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}

    for scen in scenarios:
        # A. Attendance Rule Check
        claimed_att = scen.get("claimed_attendance", 0)
        true_att = scen.get("true_attendance", 0)
        exp_att_alert = scen.get("expected_attendance_alert", False)

        ratio = true_att / float(claimed_att) if claimed_att > 0 else 1.0
        pred_att_alert = ratio < attendance_threshold_ratio

        if pred_att_alert and exp_att_alert:
            att_matrix["tp"] += 1
        elif pred_att_alert and not exp_att_alert:
            att_matrix["fp"] += 1
        elif not pred_att_alert and exp_att_alert:
            att_matrix["fn"] += 1
        else:
            att_matrix["tn"] += 1

        # B. Missing Infrastructure Rule Check
        sanc_inv = scen.get("sanctioned_inventory", {})
        true_inv = scen.get("true_inventory", {})
        exp_infra_alert = scen.get("expected_inventory_alert", False)

        pred_infra_alert = False
        for item, exp_count in sanc_inv.items():
            act_count = true_inv.get(item, 0)
            if act_count < exp_count:
                pred_infra_alert = True
                break

        if pred_infra_alert and exp_infra_alert:
            infra_matrix["tp"] += 1
        elif pred_infra_alert and not exp_infra_alert:
            infra_matrix["fp"] += 1
        elif not pred_infra_alert and exp_infra_alert:
            infra_matrix["fn"] += 1
        else:
            infra_matrix["tn"] += 1

    def calculate_rates(m: Dict[str, int]) -> Dict[str, Any]:
        tp, fp, fn, tn = m["tp"], m["fp"], m["fn"], m["tn"]
        total = tp + fp + fn + tn
        accuracy = (tp + tn) / total if total > 0 else 0.0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

        return {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "accuracy": round(accuracy, 3),
            "precision": round(prec, 3),
            "recall": round(rec, 3),
            "f1": round(f1, 3),
            "fpr": round(fpr, 3),
            "fnr": round(fnr, 3),
        }

    return {
        "attendance_alerts": calculate_rates(att_matrix),
        "infrastructure_alerts": calculate_rates(infra_matrix),
        "total_scenarios_evaluated": len(scenarios),
        "operating_parameters": {
            "attendance_threshold_ratio": attendance_threshold_ratio,
            "consecutive_windows": consecutive_windows,
        },
    }
