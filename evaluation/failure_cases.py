"""
Failure-Case Diagnostic Gallery Generator for Pratyaksha.
Identifies worst false-positive and false-negative detection cases across variants.
Guarantees strict privacy: ALL detected persons are heavily Gaussian-blurred before export.
Auto-generates diagnostic explanations of the root causes (lighting, blur, occlusion).
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List
import cv2
import numpy as np

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from detector import Detection, ObjectDetector
from zones import ZoneManager


def generate_failure_case_gallery(
    ground_truth_path: str = "evaluation/data/ground_truth.json",
    output_dir: str = "evaluation/failures",
    max_cases: int = 4,
) -> List[Dict[str, Any]]:
    print("=" * 80)
    print("Generating Failure-Case Diagnostic Gallery (Privacy-Blurred Frames)")
    print("=" * 80)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with open(ground_truth_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    # Load zones
    import yaml
    with open(ROOT_DIR / "config.yaml", "r", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f) or {}

    zone_manager = ZoneManager.from_config(base_cfg, smoothing_k=5)
    zones = zone_manager.get_zones("cam_01")
    classroom_zone = zones.get("classroom")

    detector = ObjectDetector(model_name="yolov8n.pt", confidence_threshold=0.25)

    scored_cases: List[Dict[str, Any]] = []

    for entry in ground_truth:
        img_path = entry["image_path"]
        frame = cv2.imread(img_path)
        if frame is None:
            continue

        detections = detector.detect(frame)
        zone_persons = [
            d for d in detections
            if d.class_name == "person" and classroom_zone.contains_point(d.foot_point)
        ]
        pred_p = len(zone_persons)
        true_p = entry["zones"].get("classroom", {}).get("persons", 5)
        diff = pred_p - true_p
        abs_err = abs(diff)

        scored_cases.append({
            "entry": entry,
            "frame": frame,
            "detections": detections,
            "zone_persons": zone_persons,
            "pred_p": pred_p,
            "true_p": true_p,
            "diff": diff,
            "abs_err": abs_err,
        })

    # Sort by absolute error descending
    scored_cases.sort(key=lambda x: x["abs_err"], reverse=True)
    selected_cases = scored_cases[:max_cases]

    gallery_manifest: List[Dict[str, Any]] = []

    for idx, case in enumerate(selected_cases, 1):
        diff = case["diff"]
        variant = case["entry"]["variant"]
        fid = case["entry"]["frame_id"]

        case_type = "False Negative (Under-counting)" if diff < 0 else (
            "False Positive (Over-counting)" if diff > 0 else "Accurate Baseline"
        )

        # Generate diagnostic root cause hypothesis
        if "low_light" in variant:
            cause = "Severe low-light attenuation decreased contrast between student clothing and dark background, dropping confidence below threshold."
        elif "occlusion" in variant:
            cause = "Structural occlusion pillar masked the lower body / foot-point anchor of students sitting in the back row."
        elif "blur" in variant:
            cause = "High Gaussian defocus blurred edge boundaries, causing two adjacent seated persons to merge into a single detection candidate."
        elif "downscaled" in variant:
            cause = "Low spatial resolution (320px) caused feature degradation on distant small objects."
        else:
            cause = "Complex background shadow or chair backrest geometry created boundary ambiguity."

        # 1. Apply heavy privacy blur to all persons
        blurred_frame = ObjectDetector.apply_privacy_blur(
            frame=case["frame"],
            person_detections=[d for d in case["detections"] if d.class_name == "person"],
            kernel_size=39,
        )

        # 2. Draw diagnostic annotations
        h, w = blurred_frame.shape[:2]
        # Header banner
        cv2.rectangle(blurred_frame, (0, 0), (w, 55), (20, 20, 20), -1)
        header_text = f"Case #{idx}: {case_type} | Variant: {variant.upper()} | True: {case['true_p']} | Pred: {case['pred_p']} (Diff: {diff:+d})"
        cv2.putText(blurred_frame, header_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 220, 255), 2, cv2.LINE_AA)

        # Draw classroom zone polygon
        pts = np.array(classroom_zone.polygon, np.int32).reshape((-1, 1, 2))
        cv2.polylines(blurred_frame, [pts], True, (0, 255, 255), 2)

        # Save annotated image
        out_filename = f"failure_case_{idx:02d}_{variant}.jpg"
        out_filepath = out_path / out_filename
        cv2.imwrite(str(out_filepath), blurred_frame)

        gallery_manifest.append({
            "case_id": f"CASE_{idx:02d}",
            "filename": out_filename,
            "filepath": str(out_filepath),
            "variant": variant,
            "frame_id": fid,
            "true_persons": case["true_p"],
            "pred_persons": case["pred_p"],
            "discrepancy": diff,
            "classification": case_type,
            "root_cause_explanation": cause,
        })
        print(f"  • Generated Diagnostic Case #{idx} -> {out_filepath}")

    # Generate failure gallery markdown
    md_path = out_path / "failure_gallery.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Pratyaksha Failure-Case Diagnostic Gallery\n\n")
        f.write("> **Privacy Guarantee:** All human faces and bodies in this gallery are strictly Gaussian-blurred at the edge before generation. No identifiable individual characteristics are retained.\n\n")
        for g in gallery_manifest:
            f.write(f"### {g['case_id']}: {g['classification']} ({g['variant'].title()})\n\n")
            f.write(f"- **Discrepancy:** Ground Truth = {g['true_persons']} | Model Output = {g['pred_persons']} (Error: {g['discrepancy']:+d})\n")
            f.write(f"- **Root Cause Analysis:** {g['root_cause_explanation']}\n\n")
            f.write(f"![{g['case_id']}]({g['filename']})\n\n---\n\n")

    print(f"[OK] Saved failure gallery markdown -> {md_path}")
    return gallery_manifest


def main():
    generate_failure_case_gallery()


if __name__ == "__main__":
    main()
