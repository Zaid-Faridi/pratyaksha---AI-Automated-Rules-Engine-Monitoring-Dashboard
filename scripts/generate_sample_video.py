#!/usr/bin/env python3
"""
Sample Video Generator for Pratyaksha Phase 1.
Generates a realistic 1280x720 multi-zone skilling center video:
- Zone 'classroom': desks, chairs, laptops, with students sitting/moving
- Zone 'workshop': workbenches, chairs, and trainees
Includes occlusion/movement variations across frames to demonstrate rolling median smoothing.
"""

import math
import os
from pathlib import Path
import urllib.request
import cv2
import numpy as np
from ultralytics import YOLO


def download_asset(url: str, dest_path: Path) -> bool:
    if dest_path.is_file():
        return True
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp, open(dest_path, "wb") as f:
            f.write(resp.read())
        return True
    except Exception as e:
        print(f"[WARNING] Could not download {url}: {e}")
        return False


def extract_crops(sample_dir: Path) -> dict:
    assets = {
        "person": "https://raw.githubusercontent.com/ultralytics/ultralytics/main/ultralytics/assets/zidane.jpg",
        "chair": "https://images.unsplash.com/photo-1567538096630-e0c55bd6374c?w=500",
        "table": "https://images.unsplash.com/photo-1615066390971-03e4e1c36ddf?w=500",
        "laptop": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500",
    }

    for name, url in assets.items():
        download_asset(url, sample_dir / f"{name}.jpg")

    model = YOLO("yolov8n.pt")
    crops = {"persons": [], "chair": None, "table": None, "laptop": None}

    # Extract person crops
    for p_file in ["zidane.jpg", "bus.jpg"]:
        p_path = sample_dir / p_file
        if p_path.is_file():
            img = cv2.imread(str(p_path))
            if img is not None:
                res = model(img, verbose=False)[0]
                for b in res.boxes:
                    if int(b.cls[0]) == 0 and float(b.conf[0]) > 0.5:
                        x1, y1, x2, y2 = b.xyxy[0].cpu().numpy().astype(int)
                        crop = img[y1:y2, x1:x2]
                        if crop.size > 0 and crop.shape[0] > 100:
                            crops["persons"].append(crop)

    # Extract chair
    chair_path = sample_dir / "chair.jpg"
    if chair_path.is_file():
        img = cv2.imread(str(chair_path))
        if img is not None:
            res = model(img, verbose=False)[0]
            for b in res.boxes:
                if res.names[int(b.cls[0])] == "chair" and float(b.conf[0]) > 0.4:
                    x1, y1, x2, y2 = b.xyxy[0].cpu().numpy().astype(int)
                    crops["chair"] = img[y1:y2, x1:x2]
                    break
        if crops["chair"] is None:
            crops["chair"] = img

    # Extract table
    table_path = sample_dir / "table.jpg"
    if table_path.is_file():
        img = cv2.imread(str(table_path))
        if img is not None:
            res = model(img, verbose=False)[0]
            for b in res.boxes:
                if res.names[int(b.cls[0])] == "dining table" and float(b.conf[0]) > 0.3:
                    x1, y1, x2, y2 = b.xyxy[0].cpu().numpy().astype(int)
                    crops["table"] = img[y1:y2, x1:x2]
                    break
        if crops["table"] is None:
            crops["table"] = img

    # Extract laptop
    laptop_path = sample_dir / "laptop.jpg"
    if laptop_path.is_file():
        img = cv2.imread(str(laptop_path))
        if img is not None:
            res = model(img, verbose=False)[0]
            for b in res.boxes:
                if res.names[int(b.cls[0])] == "laptop" and float(b.conf[0]) > 0.4:
                    x1, y1, x2, y2 = b.xyxy[0].cpu().numpy().astype(int)
                    crops["laptop"] = img[y1:y2, x1:x2]
                    break
        if crops["laptop"] is None:
            crops["laptop"] = img

    return crops


def overlay_crop(base: np.ndarray, crop: np.ndarray, x: int, y: int, target_w: int, target_h: int) -> None:
    """Resize and overlay a crop onto the base frame with boundary clamping."""
    resized = cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_AREA)
    H, W = base.shape[:2]

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(W, x + target_w)
    y2 = min(H, y + target_h)

    cw = x2 - x1
    ch = y2 - y1
    if cw <= 0 or ch <= 0:
        return

    base[y1:y2, x1:x2] = resized[0:ch, 0:cw]


def create_demo_video(output_path: Path, crops: dict, duration_sec: int = 15, fps: int = 10) -> None:
    W, H = 1280, 720
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (W, H))

    total_frames = duration_sec * fps
    print(f"[INFO] Rendering synthetic skilling center video ({total_frames} frames)...")

    # Person crops fallback
    persons = crops.get("persons")
    if not persons:
        # Fallback dummy person if no crop
        dummy = np.full((200, 100, 3), 120, dtype=np.uint8)
        persons = [dummy]

    chair_crop = crops.get("chair")
    table_crop = crops.get("table")
    laptop_crop = crops.get("laptop")

    for f_idx in range(total_frames):
        # 1. Base room background (skilling center aesthetic floor and walls)
        frame = np.full((H, W, 3), (230, 230, 230), dtype=np.uint8)
        # Floor
        cv2.rectangle(frame, (0, 300), (W, H), (210, 215, 218), -1)
        # Divider wall / pillar
        cv2.rectangle(frame, (630, 0), (650, H), (180, 180, 180), -1)

        # 2. Left Zone: Classroom (x: 40..620, y: 40..680)
        # Sanctioned infrastructure:
        # 2 tables/benches
        if table_crop is not None:
            overlay_crop(frame, table_crop, 80, 260, 220, 130)
            overlay_crop(frame, table_crop, 360, 260, 220, 130)

        # 4 computers/laptops on tables
        if laptop_crop is not None:
            overlay_crop(frame, laptop_crop, 100, 240, 75, 55)
            overlay_crop(frame, laptop_crop, 200, 240, 75, 55)
            overlay_crop(frame, laptop_crop, 380, 240, 75, 55)
            overlay_crop(frame, laptop_crop, 480, 240, 75, 55)

        # 4 chairs
        if chair_crop is not None:
            overlay_crop(frame, chair_crop, 90, 380, 85, 120)
            overlay_crop(frame, chair_crop, 200, 380, 85, 120)
            overlay_crop(frame, chair_crop, 370, 380, 85, 120)
            overlay_crop(frame, chair_crop, 480, 380, 85, 120)

        # Classroom Students (Persons):
        # Student 1: sitting at desk 1
        p0 = persons[0 % len(persons)]
        overlay_crop(frame, p0, 95, 300, 80, 180)

        # Student 2: sitting at desk 2
        p1 = persons[1 % len(persons)]
        overlay_crop(frame, p1, 375, 300, 80, 180)

        # Student 3: walking in classroom, demonstrates movement and occlusion
        # Every 4th second, student 3 gets temporarily occluded/steps behind a whiteboard
        occluded = (f_idx % 40) >= 30
        if not occluded:
            p2 = persons[2 % len(persons)]
            walk_x = 220 + int(40 * math.sin(f_idx * 0.15))
            overlay_crop(frame, p2, walk_x, 340, 85, 190)

        # 3. Right Zone: Workshop (x: 660..1240, y: 40..680)
        # Sanctioned infrastructure:
        # 2 workbenches
        if table_crop is not None:
            overlay_crop(frame, table_crop, 700, 280, 240, 140)
            overlay_crop(frame, table_crop, 980, 280, 240, 140)

        # 2 chairs
        if chair_crop is not None:
            overlay_crop(frame, chair_crop, 740, 420, 90, 130)
            overlay_crop(frame, chair_crop, 1020, 420, 90, 130)

        # Workshop Trainee:
        p_work = persons[min(1, len(persons) - 1)]
        overlay_crop(frame, p_work, 750, 300, 90, 200)

        out.write(frame)

    out.release()
    print(f"[SUCCESS] Sample video generated at '{output_path}'")


def main() -> None:
    sample_dir = Path("sample_data")
    sample_dir.mkdir(parents=True, exist_ok=True)
    output_video = sample_dir / "skilling_center_demo.mp4"

    crops = extract_crops(sample_dir)
    create_demo_video(output_video, crops, duration_sec=12, fps=10)


if __name__ == "__main__":
    main()
