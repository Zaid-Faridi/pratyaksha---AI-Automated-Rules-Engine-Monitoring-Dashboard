#!/usr/bin/env python3
"""
Interactive Zone Drawer Helper for Pratyaksha.
Allows administrators to click and draw named ROI polygons on a sample video frame,
configure expected infrastructure inventory, and save directly to config.yaml.

Usage:
    python draw_zones.py --source sample_data/sample.mp4 --camera-id cam_01 --config config.yaml
    python draw_zones.py --image sample_frame.jpg --camera-id cam_01 --config config.yaml
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
import yaml


class ZoneDrawer:
    def __init__(self, frame: np.ndarray, config_path: str, camera_id: str) -> None:
        self.base_frame = frame.copy()
        self.display_frame = frame.copy()
        self.config_path = Path(config_path)
        self.camera_id = camera_id

        self.current_polygon: List[Tuple[int, int]] = []
        self.saved_zones: Dict[str, Dict[str, Any]] = {}
        self.window_name = f"Pratyaksha Zone Drawer - {camera_id} (Click points | 'c': Close | 's': Save | 'r': Reset | 'q': Quit)"

        self._load_existing_zones()

    def _load_existing_zones(self) -> None:
        """Load any existing zones from config.yaml if present."""
        if self.config_path.is_file():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                cams = data.get("cameras", {})
                if self.camera_id in cams:
                    self.saved_zones = cams[self.camera_id].get("zones", {}) or {}
                    print(f"[INFO] Loaded {len(self.saved_zones)} existing zones for '{self.camera_id}'.")

    def _mouse_callback(self, event: int, x: int, y: int, flags: int, param: Any) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self.current_polygon.append((x, y))
            print(f"  • Point added: ({x}, {y})")
            self._redraw()

    def _redraw(self) -> None:
        self.display_frame = self.base_frame.copy()

        # Draw already saved zones
        palette = [
            (0, 165, 255),  # Orange
            (255, 128, 0),  # Sky blue
            (0, 200, 0),    # Green
            (200, 0, 200),  # Magenta
            (0, 255, 255),  # Yellow
        ]

        for idx, (z_name, z_info) in enumerate(self.saved_zones.items()):
            pts = np.array(z_info["polygon"], dtype=np.int32).reshape((-1, 1, 2))
            color = palette[idx % len(palette)]
            overlay = self.display_frame.copy()
            cv2.fillPoly(overlay, [pts], color)
            cv2.addWeighted(overlay, 0.25, self.display_frame, 0.75, 0, self.display_frame)
            cv2.polylines(self.display_frame, [pts], isClosed=True, color=color, thickness=2)

            if len(z_info["polygon"]) > 0:
                p0 = z_info["polygon"][0]
                cv2.putText(
                    self.display_frame,
                    f"Zone: {z_name}",
                    (p0[0], max(20, p0[1] - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                    cv2.LINE_AA,
                )

        # Draw current polygon in progress
        if self.current_polygon:
            pts = np.array(self.current_polygon, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(self.display_frame, [pts], isClosed=False, color=(0, 255, 255), thickness=2)
            for pt in self.current_polygon:
                cv2.circle(self.display_frame, pt, 4, (0, 0, 255), -1)

        cv2.imshow(self.window_name, self.display_frame)

    def _close_and_record_polygon(self) -> None:
        if len(self.current_polygon) < 3:
            print("[WARNING] A polygon must have at least 3 vertices.")
            return

        print("\n" + "=" * 50)
        print("CONFIGURING COMPLETED ZONE")
        print("=" * 50)
        zone_name = input("Enter zone identifier (e.g. 'classroom_a', 'welding_bay'): ").strip()
        if not zone_name:
            zone_name = f"zone_{len(self.saved_zones) + 1}"

        print("Enter expected infrastructure items in key:count format separated by commas.")
        print("Example: chair: 15, bench: 6, computer: 10")
        infra_input = input("Expected infrastructure (press Enter for none): ").strip()

        expected_dict: Dict[str, int] = {}
        if infra_input:
            parts = [p.strip() for p in infra_input.split(",") if p.strip()]
            for p in parts:
                if ":" in p:
                    item, count_str = p.split(":", 1)
                    try:
                        expected_dict[item.strip().lower()] = int(count_str.strip())
                    except ValueError:
                        print(f"[WARNING] Skipping invalid entry '{p}'")

        self.saved_zones[zone_name] = {
            "polygon": [[int(pt[0]), int(pt[1])] for pt in self.current_polygon],
            "expected_infrastructure": expected_dict,
        }
        print(f"[SUCCESS] Zone '{zone_name}' registered with {len(self.current_polygon)} vertices.")
        self.current_polygon = []
        self._redraw()

    def _save_to_yaml(self) -> None:
        config_data: Dict[str, Any] = {}
        if self.config_path.is_file():
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}

        config_data.setdefault("cameras", {})
        config_data["cameras"].setdefault(self.camera_id, {})
        config_data["cameras"][self.camera_id]["zones"] = self.saved_zones

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, sort_keys=False, indent=2)

        print(f"\n[SAVED] {len(self.saved_zones)} zone(s) written to '{self.config_path}' under camera '{self.camera_id}'.")

    def run(self) -> None:
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window_name, self._mouse_callback)
        self._redraw()

        print("\nInteractive Zone Drawer Controls:")
        print("  • Left Click : Place polygon vertex")
        print("  • 'c'        : Close polygon and enter zone details")
        print("  • 'r'        : Reset current in-progress polygon")
        print("  • 'd'        : Delete last saved zone")
        print("  • 's'        : Save all zones to config.yaml")
        print("  • 'q' / ESC  : Quit\n")

        while True:
            key = cv2.waitKey(20) & 0xFF
            if key in (27, ord("q")):
                break
            elif key == ord("c"):
                self._close_and_record_polygon()
            elif key == ord("r"):
                self.current_polygon = []
                print("[INFO] Current polygon cleared.")
                self._redraw()
            elif key == ord("d"):
                if self.saved_zones:
                    removed = self.saved_zones.popitem()
                    print(f"[INFO] Removed zone '{removed[0]}'.")
                    self._redraw()
            elif key == ord("s"):
                self._save_to_yaml()

        cv2.destroyAllWindows()


def extract_sample_frame(source_path: str) -> np.ndarray:
    path = Path(source_path)
    if not path.is_file() and not source_path.startswith("rtsp://"):
        raise FileNotFoundError(f"Source file '{source_path}' does not exist.")

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video stream at '{source_path}'")

    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError("Failed to extract a frame from video stream.")

    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Pratyaksha Helper: Interactive ROI Polygon Zone Drawer")
    parser.add_argument("--source", type=str, default=None, help="Video file or RTSP stream URL to extract a sample frame from.")
    parser.add_argument("--image", type=str, default=None, help="Direct path to an image file to draw zones on.")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config.yaml to load/save zones.")
    parser.add_argument("--camera-id", type=str, default="cam_01", help="Camera identifier.")
    args = parser.parse_args()

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"[ERROR] Could not load image from '{args.image}'", file=sys.stderr)
            sys.exit(1)
    elif args.source:
        frame = extract_sample_frame(args.source)
    else:
        # Check if config has a source for this camera
        config_path = Path(args.config)
        if config_path.is_file():
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                source = cfg.get("cameras", {}).get(args.camera_id, {}).get("source")
                if source and Path(source).is_file():
                    frame = extract_sample_frame(source)
                else:
                    print("[ERROR] Please provide --source <video_file> or --image <image_file>.", file=sys.stderr)
                    sys.exit(1)
        else:
            print("[ERROR] Please provide --source <video_file> or --image <image_file>.", file=sys.stderr)
            sys.exit(1)

    drawer = ZoneDrawer(frame, config_path=args.config, camera_id=args.camera_id)
    drawer.run()


if __name__ == "__main__":
    main()
