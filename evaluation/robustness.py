"""
Robustness and Profile Degradation Evaluation for Pratyaksha.
Measures detection accuracy under:
- Environmental degradations: baseline, low light, blur, downscaled, compression, occlusion.
- Operational profiles: ultra_low (320px), low (480px), normal (640px).
- Associates latency and throughput (FPS) metrics with detection resilience.
"""

import csv
import json
from pathlib import Path
import sys
from typing import Any, Dict, List
import cv2
import matplotlib.pyplot as plt
import numpy as np

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from edge.config import PROFILES
from edge.detector_runtime import EdgeDetectorRuntime
from zones import ZoneManager


def evaluate_robustness(
    ground_truth_path: str = "evaluation/data/ground_truth.json",
    charts_dir: str = "evaluation/charts",
    tables_dir: str = "evaluation/tables",
) -> List[Dict[str, Any]]:
    print("=" * 80)
    print("Executing Robustness Evaluation across Environmental Degradations & Edge Profiles")
    print("=" * 80)

    with open(ground_truth_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    # Load Zone manager
    base_cfg_path = ROOT_DIR / "config.yaml"
    import yaml
    with open(base_cfg_path, "r", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f) or {}

    zone_manager = ZoneManager.from_config(base_cfg, smoothing_k=5)
    zones = zone_manager.get_zones("cam_01")

    # Load ONNX or PyTorch detector
    detector = EdgeDetectorRuntime(
        model_path="yolov8n.pt",
        onnx_path="yolov8n.onnx",
        prefer_onnx=True,
    )

    variants = ["baseline", "low_light", "blur", "downscaled", "compression", "occlusion"]
    profile_names = ["ultra_low", "low", "normal"]

    # Benchmark baseline metrics (from Phase 4 hardware benchmarks)
    benchmark_lookup = {
        "ultra_low": {"latency_ms": 9.2, "fps": 109.3, "res": 320},
        "low": {"latency_ms": 22.2, "fps": 45.0, "res": 480},
        "normal": {"latency_ms": 33.4, "fps": 30.0, "res": 640},
    }

    robustness_rows: List[Dict[str, Any]] = []

    for p_name in profile_names:
        profile_spec = PROFILES[p_name]
        imgsz = profile_spec.input_resolution
        bench = benchmark_lookup[p_name]

        for variant in variants:
            var_entries = [e for e in ground_truth if e.get("variant") == variant]
            if not var_entries:
                continue

            person_diffs = []
            for entry in var_entries:
                img = cv2.imread(entry["image_path"])
                if img is None:
                    continue

                dets = detector.detect(img, imgsz=imgsz)

                # Count classroom persons
                zone = zones.get("classroom")
                if zone:
                    pred_p = len([
                        d for d in dets
                        if d.class_name == "person" and zone.contains_point(d.foot_point)
                    ])
                    true_p = entry["zones"].get("classroom", {}).get("persons", 5)
                    person_diffs.append(abs(pred_p - true_p))

            mae = float(np.mean(person_diffs)) if person_diffs else 0.0
            rmse = float(np.sqrt(np.mean(np.square(person_diffs)))) if person_diffs else 0.0
            accuracy_pct = max(0.0, 100.0 - (mae / 5.0 * 100.0))

            robustness_rows.append({
                "profile": p_name,
                "variant": variant,
                "input_resolution": f"{imgsz}x{imgsz}",
                "person_mae": round(mae, 2),
                "person_rmse": round(rmse, 2),
                "accuracy_pct": round(accuracy_pct, 1),
                "latency_ms": bench["latency_ms"],
                "fps": bench["fps"],
                "sample_interval": f"{profile_spec.sample_interval_sec}s",
            })

    # Save to CSV
    Path(tables_dir).mkdir(parents=True, exist_ok=True)
    csv_file = Path(tables_dir) / "robustness_table.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(robustness_rows[0].keys()))
        writer.writeheader()
        writer.writerows(robustness_rows)
    print(f"[OK] Saved robustness metrics -> {csv_file}")

    # Plot Robustness Chart
    Path(charts_dir).mkdir(parents=True, exist_ok=True)
    chart_file = Path(charts_dir) / "robustness_comparison.png"

    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=300)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    x = np.arange(len(variants))
    width = 0.25

    colors = {"ultra_low": "#f97316", "low": "#38bdf8", "normal": "#2563eb"}

    for i, p_name in enumerate(profile_names):
        subset = [r for r in robustness_rows if r["profile"] == p_name]
        maes = [r["person_mae"] for r in subset]
        offset = (i - 1) * width
        rects = ax.bar(x + offset, maes, width, label=f"Profile '{p_name}' ({PROFILES[p_name].input_resolution}px)", color=colors[p_name])
        # Value labels on top of bars
        for rect in rects:
            height = rect.get_height()
            ax.annotate(
                f"{height:.1f}",
                xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center", va="bottom", fontsize=8,
            )

    ax.set_ylabel("Person Count MAE (Lower is Better)", fontsize=11)
    ax.set_title("Detection Robustness across Environmental Degradations & Edge Profiles", fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([v.replace("_", " ").title() for v in variants], fontsize=10)
    ax.legend(loc="upper left", frameon=True)
    ax.set_ylim(0, max(r["person_mae"] for r in robustness_rows) + 1.2)

    plt.tight_layout()
    plt.savefig(chart_file)
    plt.close()
    print(f"[OK] Saved robustness comparison chart -> {chart_file}")

    return robustness_rows


def main():
    evaluate_robustness()


if __name__ == "__main__":
    main()
