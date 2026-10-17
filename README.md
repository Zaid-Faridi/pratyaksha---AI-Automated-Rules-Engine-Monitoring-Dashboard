# Pratyaksha (प्रत्यक्ष) - Phase 1: Detection Pipeline
> **AI Video-Analytics System for Monitoring Government Skilling Centres**  
> *MSDE Problem Statement 26245*

Pratyaksha is a privacy-first video-analytics pipeline designed to monitor government-sponsored skilling centres under low-bandwidth, varying lighting, and commodity camera conditions. It computes real attendance counts per zone, reconciles physical infrastructure against sanctioned inventory (workbenches, machines, chairs, computers), and audits discrepancies without compromising personal privacy.

---

## Key Features & Architecture

1. **Configurable Frame Sampling**:
   - Ingests pre-recorded video files or live network streams (`rtsp://`).
   - Time-based frame sampling (production default: 30s; testing: 1–2s).
   - Fast-forwards video files using timestamp seeks without decoding redundant intermediate frames.

2. **Named ROI Polygons & Zone Management (`zones.py`)**:
   - Load custom polygons for classroom bays, workshop areas, and lab zones from `config.yaml`.
   - Point-in-polygon containment uses ground-plane foot anchors (`(x, y2)`) for people to prevent false zone assignments caused by body perspective angles, and center points for stationary furniture.

3. **Temporal Occlusion Smoothing**:
   - Applies a rolling median filter over the last $K$ samples (default $K=5$) to smooth transient occlusions (e.g. students walking behind whiteboards or pillars).

4. **Sanctioned Infrastructure Audit**:
   - Detects chairs, workbenches (`dining table`, `bench` proxies), and computers (`laptop`, `tv/monitor`).
   - Reconciles detected counts against sanctioned expectations, reporting `MATCH`, `DEFICIT`, or `SURPLUS`.

5. **Privacy by Design**:
   - **No biometric or facial identification**: No facial crops, identity signatures, or person cutouts are ever extracted, transmitted, or stored.
   - **Anonymized Diagnostics**: Visual frame saving is **OFF by default**. When explicitly enabled with `--save-annotated`, all detected persons undergo heavy Gaussian blur before frames are written to disk.

6. **Audit-Ready Structured Output**:
   - Emits a clean terminal summary per sample.
   - Appends structured records to a JSON Lines (`.jsonl`) file for downstream auditing.

---

## Directory Structure

```
Pratyaksha/
├── config.yaml                     # Zone polygons, expected inventory, and pipeline config
├── detector.py                     # Ultralytics YOLO detector & privacy blur engine
├── draw_zones.py                   # Interactive OpenCV helper to draw & save zone polygons
├── pipeline.py                     # Ingestion, sampling, zone audit, and JSON Lines logger
├── run.py                          # CLI entrypoint with flexible arguments
├── requirements.txt                # Python package dependencies
├── .gitignore                      # Git ignore rules for virtual environments & model weights
├── scripts/
│   └── generate_sample_video.py    # Generates a synthetic multi-zone skilling center video
├── sample_data/
│   └── skilling_center_demo.mp4    # Generated demonstration video (classroom + workshop)
└── outputs/
    ├── detections.jsonl            # Sample JSON Lines audit logs
    └── frames/                     # Diagnostic frames with blurred persons (optional)
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+ (Tested on Python 3.11 / 3.12)
- macOS, Linux, or Windows

### 1. Create and Activate Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv .venv

# Activate on macOS / Linux:
source .venv/bin/activate

# Or on Windows:
# .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

*(Note: Ultralytics will automatically fetch the lightweight `yolov8n.pt` nano model weights on first execution).*

---

## Quickstart & Verification Test

### 1. Generate the Skilling Centre Sample Video
If you want to test immediately without an external video file or camera, generate our synthetic test video containing classroom and workshop zones with people and infrastructure:

```bash
python scripts/generate_sample_video.py
```
This produces `sample_data/skilling_center_demo.mp4` with moving trainees, desks, laptops, and chairs.

### 2. Run the Detection Pipeline

Run the pipeline with a 1-second sampling interval and privacy-preserving frame saving:

```bash
python run.py \
  --config config.yaml \
  --source sample_data/skilling_center_demo.mp4 \
  --sample-interval 1 \
  --save-annotated
```

### Terminal Output Preview:
```text
======================================================================
[SAMPLE #0006] 2023-11-14T22:13:25Z | Camera: cam_01
======================================================================
Zone: 'classroom'
  • Attendance (Persons) : Raw =  5 | Smoothed (Rolling Median K=5) =  5
  • Sanctioned Infrastructure Audit:
      - chair       : Expected =  6 | Detected =  4 | Diff =  -2 | Status: [ALERT DEFICIT]
      - bench       : Expected =  2 | Detected =  2 | Diff =   0 | Status: [OK]
      - computer    : Expected =  4 | Detected =  4 | Diff =   0 | Status: [OK]
----------------------------------------------------------------------
Zone: 'workshop'
  • Attendance (Persons) : Raw =  1 | Smoothed (Rolling Median K=5) =  1
  • Sanctioned Infrastructure Audit:
      - workbench   : Expected =  2 | Detected =  2 | Diff =   0 | Status: [OK]
      - chair       : Expected =  4 | Detected =  4 | Diff =   0 | Status: [OK]
----------------------------------------------------------------------
[PRIVACY] Anonymized frame saved (persons blurred): outputs/frames/cam_01_sample_0006.jpg
```

---

## Interactive Zone Polygon Drawer (`draw_zones.py`)

To configure new zones on an existing camera frame or RTSP feed:

```bash
python draw_zones.py --source sample_data/skilling_center_demo.mp4 --camera-id cam_01 --config config.yaml
```

### Controls:
- **Left Click**: Add polygon vertices on the window.
- **`c`**: Close polygon and enter the zone name and expected infrastructure in the console prompt.
- **`r`**: Reset the current in-progress polygon.
- **`d`**: Delete the last saved zone.
- **`s`**: Save all zones directly into `config.yaml`.
- **`q` / `ESC`**: Exit the drawer.

---

## Configuration Reference (`config.yaml`)

```yaml
pipeline:
  sample_interval_sec: 30       # Sampling frequency (seconds)
  smoothing_window_k: 5         # Rolling median window size
  model_name: "yolov8n.pt"      # YOLO nano model for lightweight edge inference
  confidence_threshold: 0.25    # Minimum detection confidence
  save_annotated_frames: false  # Privacy default: False
  annotated_dir: "outputs/frames"
  output_jsonl: "outputs/detections.jsonl"
  person_blur_strength: 35      # Gaussian blur kernel size for privacy anonymization

class_mapping:
  chair: ["chair"]
  bench: ["bench", "dining table"]
  workbench: ["dining table", "bench"]
  computer: ["laptop", "tv"]

cameras:
  cam_01:
    source: "sample_data/skilling_center_demo.mp4" # or "rtsp://admin:pass@192.168.1.50:554/live"
    zones:
      classroom:
        polygon:
          - [40, 40]
          - [620, 40]
          - [620, 680]
          - [40, 680]
        expected_infrastructure:
          chair: 6
          bench: 2
          computer: 4
```

---

## JSON Lines Output Schema

Every processed sample appends one JSON object per zone to `outputs/detections.jsonl`:

```json
{
  "timestamp": "2026-10-16T13:54:20Z",
  "camera_id": "cam_01",
  "zone": "classroom",
  "person_count": {
    "raw": 5,
    "smoothed": 5
  },
  "infrastructure": [
    {
      "item": "chair",
      "expected": 6,
      "detected": 4,
      "status": "DEFICIT"
    },
    {
      "item": "bench",
      "expected": 2,
      "detected": 2,
      "status": "MATCH"
    },
    {
      "item": "computer",
      "expected": 4,
      "detected": 4,
      "status": "MATCH"
    }
  ]
}
```

---

## Command-Line Options (`run.py`)

| Flag | Type | Description |
|---|---|---|
| `--config` | `str` | Path to YAML configuration file (default: `config.yaml`) |
| `--source` | `str` | Video file path or RTSP stream URL override |
| `--camera-id` | `str` | Target camera ID defined in config |
| `--sample-interval` | `float` | Sampling interval in seconds (default: 30) |
| `--smoothing-k` | `int` | Rolling median smoothing window size $K$ (default: 5) |
| `--save-annotated` | flag | Save privacy-anonymized diagnostic frames with blurred persons |
| `--output` | `str` | Destination file path for JSON Lines audit output |
| `--max-samples` | `int` | Exit after processing $N$ samples (useful for automated testing) |
| `--confidence` | `float` | YOLO detection confidence threshold override |
