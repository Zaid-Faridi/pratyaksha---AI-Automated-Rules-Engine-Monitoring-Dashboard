#!/usr/bin/env python3
"""
Pratyaksha - AI Video Analytics for Monitoring Government Skilling Centres
Phase 1: Detection Pipeline CLI Entrypoint

Usage:
    python run.py --config config.yaml
    python run.py --config config.yaml --source sample_data/test.mp4 --sample-interval 2 --save-annotated
"""

import argparse
import sys
from pathlib import Path
import yaml

from pipeline import PratyakshaPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pratyaksha Phase 1: Video Analytics Detection Pipeline for Skilling Centres (MSDE 26245)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to YAML configuration file containing zone definitions and pipeline settings.",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Optional override for video file path or RTSP stream URL.",
    )
    parser.add_argument(
        "--camera-id",
        type=str,
        default=None,
        help="Camera ID to process from configuration (defaults to first camera defined).",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=None,
        help="Frame sampling interval in seconds (default 30s in production, 1-2s for rapid testing).",
    )
    parser.add_argument(
        "--smoothing-k",
        type=int,
        default=None,
        help="Rolling median window size K for occlusion/movement smoothing.",
    )
    parser.add_argument(
        "--save-annotated",
        action="store_true",
        default=False,
        help="Save anonymized diagnostic frames (all detected persons are heavily blurred for privacy). Default is OFF.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Destination path for JSON Lines results audit log (e.g., outputs/detections.jsonl).",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum number of sampled frames to process before exiting (useful for testing).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=None,
        help="YOLO detection confidence threshold override (e.g. 0.25).",
    )
    return parser.parse_args()


def load_yaml_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.is_file():
        print(f"[ERROR] Configuration file '{config_path}' not found.", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    args = parse_args()
    config = load_yaml_config(args.config)

    # Apply command-line overrides to config if supplied
    if args.smoothing_k is not None:
        config.setdefault("pipeline", {})["smoothing_window_k"] = args.smoothing_k
    if args.confidence is not None:
        config.setdefault("pipeline", {})["confidence_threshold"] = args.confidence

    try:
        pipeline = PratyakshaPipeline(
            config=config,
            camera_id=args.camera_id,
            source_override=args.source,
            sample_interval_override=args.sample_interval,
            save_annotated_override=args.save_annotated if args.save_annotated else None,
            output_jsonl_override=args.output,
        )
        pipeline.run(max_samples=args.max_samples)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
