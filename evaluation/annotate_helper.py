"""
Ground Truth Annotation Helper Utility for Pratyaksha.
Allows inspecting ground-truth annotations, generating CSV templates for manual labeling,
and registering new ground-truth frames.
"""

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def export_csv_template(output_csv: str = "evaluation/data/ground_truth_template.csv") -> None:
    """Generate empty CSV template for manual ground-truth labeling."""
    headers = [
        "frame_id",
        "image_path",
        "variant",
        "zone",
        "true_person_count",
        "true_chair_count",
        "true_table_count",
        "true_laptop_count",
        "notes",
    ]

    p = Path(output_csv)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        # Sample template rows
        writer.writerow(["sample_001", "evaluation/data/scenarios/baseline/frame_000.jpg", "baseline", "classroom", 5, 6, 2, 2, "Normal classroom seating"])
        writer.writerow(["sample_002", "evaluation/data/scenarios/baseline/frame_000.jpg", "baseline", "workshop", 1, 2, 2, 0, "Workshop practical bench"])

    print(f"[OK] Generated ground truth CSV template: {output_csv}")


def convert_csv_to_json(csv_path: str, json_path: str = "evaluation/data/ground_truth.json") -> None:
    """Import labeled CSV into standard ground_truth.json format."""
    records_by_frame: Dict[str, Dict[str, Any]] = {}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fid = row["frame_id"]
            if fid not in records_by_frame:
                records_by_frame[fid] = {
                    "frame_id": fid,
                    "variant": row.get("variant", "baseline"),
                    "image_path": row.get("image_path", ""),
                    "zones": {},
                }
            zone_name = row["zone"]
            records_by_frame[fid]["zones"][zone_name] = {
                "persons": int(row.get("true_person_count", 0)),
                "chair": int(row.get("true_chair_count", 0)),
                "table": int(row.get("true_table_count", 0)),
                "laptop": int(row.get("true_laptop_count", 0)),
            }

    data = list(records_by_frame.values())
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] Successfully imported {len(data)} frames from {csv_path} to {json_path}")


def inspect_ground_truth(json_path: str = "evaluation/data/ground_truth.json", frame_id: str = None) -> None:
    """Print ground-truth summary from JSON."""
    if not Path(json_path).exists():
        print(f"[ERROR] {json_path} does not exist.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if frame_id:
        filtered = [f for f in data if f.get("frame_id") == frame_id]
        print(json.dumps(filtered, indent=2))
    else:
        print(f"Total Annotated Frames: {len(data)}")
        variants = {}
        for d in data:
            v = d.get("variant", "unknown")
            variants[v] = variants.get(v, 0) + 1
        print("Frames per Variant:")
        for v, cnt in variants.items():
            print(f"  • {v:<15}: {cnt} frames")


def main():
    parser = argparse.ArgumentParser(description="Pratyaksha Ground Truth Annotation Helper")
    parser.add_argument("--template", type=str, nargs="?", const="evaluation/data/ground_truth_template.csv", help="Generate CSV template")
    parser.add_argument("--import-csv", type=str, help="Import labeled CSV to ground_truth.json")
    parser.add_argument("--inspect", action="store_true", help="Inspect ground truth JSON statistics")
    parser.add_argument("--frame", type=str, help="Inspect specific frame ID")
    args = parser.parse_args()

    if args.template:
        export_csv_template(args.template)
    elif args.import_csv:
        convert_csv_to_json(args.import_csv)
    else:
        inspect_ground_truth(frame_id=args.frame)


if __name__ == "__main__":
    main()
