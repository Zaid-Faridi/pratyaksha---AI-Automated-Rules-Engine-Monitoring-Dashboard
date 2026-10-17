# Pratyaksha Edge: Low-Bandwidth Edge Agent & Deployment Mode (Phase 4)

The **Pratyaksha Edge Agent** is a resilient, privacy-preserving video analytics service engineered for deployment in rural and semi-urban government skilling centres (MSDE Problem Statement 26245). It operates autonomously on low-power hardware, tolerates extended connectivity outages, and synchronizes data with an ultra-low bandwidth footprint (< 2 KB per sample).

---

## 1. Key Architectural Features

- **Offline-First SQLite Outbox:** Every detection is written to a local transaction-safe SQLite outbox (`edge/data/outbox.db` in WAL mode) before upload. During network outages, data accumulates locally with zero loss.
- **End-to-End Idempotency:** Each event receives a unique UUID (`event_id`). The backend detects and skips duplicates automatically upon reconnection.
- **Payload Minimisation:** Compact JSON format compressed with `gzip`. Real-world sample payloads compress to **~245 bytes** (well under the 2 KB target).
- **Privacy-Preserving Evidence Thumbnails:** Strictly generated only when local alerts trigger (attendance deficit or missing sanctioned inventory). Frames are downscaled to $\le 320\text{ px}$ width, compressed to JPEG quality 50 (~5 KB), and **all persons are heavily blurred before saving to disk**.
- **Adaptive Resource Profiles:** Dynamically throttles sampling rate and input resolution between `normal`, `low`, and `ultra_low` based on local CPU temperature/load and outbox queue backup.
- **Local Pre-Checks & Compute Preservation:** Caches approved training batch schedules and sanctioned inventory locally, skipping inference outside batch hours to save power and thermal stress.
- **Optimized CPU Inference:** Runs YOLO nano using **ONNX Runtime (CPU)** with dynamic shapes, achieving ~9–33 ms latency on modern CPUs.
- **Zero Raw Video Retention:** Video frames are processed in volatile memory and immediately discarded. No video is ever stored locally or transmitted to the cloud.

---

## 2. Recommended Hardware Specifications

| Tier | Target Device | Specs | Recommended Profile | Cost Estimate |
| :--- | :--- | :--- | :--- | :--- |
| **Budget Edge** | Raspberry Pi 4 Model B | 4-core Cortex-A72 @ 1.5 GHz, 2GB/4GB RAM | `low` or `ultra_low` | ~$45–$55 |
| **High Performance Edge** | Raspberry Pi 5 | 4-core Cortex-A76 @ 2.4 GHz, 4GB RAM | `normal` or `low` | ~$60–$80 |
| **Field Mini PC (Best)** | Intel N100 / N95 Mini PC | 4-core Intel N100 up to 3.4 GHz, 8GB DDR5, 128GB SSD | `normal` | ~$120–$150 |
| **Industrial Rugged** | Jetson Orin Nano | 6-core ARM Cortex-A78AE, Ampere GPU, 4GB RAM | `normal` (GPU accelerated) | ~$200–$250 |

---

## 3. Measured Bandwidth Consumption (Per Profile)

*Measurements taken using the Pratyaksha Network Simulator on active video streams:*

| Profile | Sample Interval | Input Res | Samples/Hr | Metadata Transferred | Privacy Thumbnails | Total Data Rate | 8-Hour Shift Total |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ultra_low` | **60s** | 320x320 | 60 | 894 Bytes (~0.9 KB) | 0 (Disabled) | **~0.9 KB / hr** | **~0.01 MB / day** |
| `low` | **30s** | 480x480 | 120 | 3.3 KB | 2 / hr (Critical only) | **~14.6 KB / hr** | **~0.11 MB / day** |
| `normal` | **15s** | 640x640 | 240 | 12.5 KB | 6 / hr (Standard) | **~46.3 KB / hr** | **~0.36 MB / day** |

> [!NOTE]
> Under `ultra_low` mode, a skilling centre can operate on 2G/EDGE or saturated satellite connections using less than **10 KB per workday**.

---

## 4. Setup and Installation

### Option A: Local Python Environment

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Export YOLO nano model to ONNX for CPU acceleration
python edge/export_onnx.py --model yolov8n.pt --output yolov8n.onnx

# 3. Benchmark profiles on your local CPU
python edge/benchmark.py

# 4. Start the Edge Monitoring Agent
python -m edge.agent --config edge/edge_config.yaml --profile normal
```

### Option B: Docker Container (CPU-only, Non-root)

```bash
# 1. Build and run using Docker Compose
docker compose -f edge/docker-compose.yml up -d

# 2. View container logs
docker compose -f edge/docker-compose.yml logs -f
```

### Option C: Systemd Field Service (Raspberry Pi / Linux Mini PC)

```bash
# 1. Copy service definition
sudo cp edge/pratyaksha-edge.service /etc/systemd/system/

# 2. Create configuration directories
sudo mkdir -p /etc/pratyaksha /var/lib/pratyaksha/data /var/log/pratyaksha
sudo cp edge/edge_config.yaml /etc/pratyaksha/

# 3. Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable pratyaksha-edge
sudo systemctl start pratyaksha-edge
sudo systemctl status pratyaksha-edge
```

---

## 5. Network Fault & Outage Simulation

To verify crash safety, queue persistence, and cloud synchronization under degraded conditions:

```bash
# Run the end-to-end network outage, recovery, and idempotency simulator
python edge/network_simulator.py --backend http://127.0.0.1:8088
```

The simulator verifies:
1. Normal online baseline synchronization.
2. Sudden network disconnection: incoming events buffer into SQLite with zero loss.
3. Network restoration: outbox automatically drains all accumulated events in compressed batches.
4. Idempotency check: duplicate event UUIDs are rejected by the backend with zero duplicate entries.
5. Exact bandwidth audit report per profile.

---

## 6. Configuration Parameters (`edge_config.yaml`)

| Parameter | Environment Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `edge.centre_id` | `PRATYAKSHA_CENTRE_ID` | `centre_01` | Unique Government Centre Identifier |
| `edge.camera_id` | `PRATYAKSHA_CAMERA_ID` | `cam_01` | Unique Camera ID |
| `edge.source` | `PRATYAKSHA_CAMERA_SOURCE` | RTSP / demo video | Video capture stream |
| `backend.url` | `PRATYAKSHA_BACKEND_URL` | `http://127.0.0.1:8088` | Pratyaksha FastAPI Backend URL |
| `backend.api_key` | `PRATYAKSHA_API_KEY` | `null` | Per-centre authentication header (`X-API-Key`) |
| `adaptive.profile` | `PRATYAKSHA_PROFILE` | `normal` | Initial profile (`ultra_low`, `low`, `normal`) |
| `storage.daily_budget_bytes` | — | `52428800` (50 MB) | Daily upload budget limit before dropping thumbnails |

---

## 7. Troubleshooting Guide

- **Camera Reconnect Loops:**
  - Check RTSP stream URL with `ffplay rtsp://<camera-ip>:554/live` or `cv2.VideoCapture`.
  - The edge agent automatically backs off exponentially up to 60s during stream loss.
- **Outbox Queue Growing (`queue_depth > 100`):**
  - Verify network connectivity to `PRATYAKSHA_BACKEND_URL`.
  - Check `edge/data/edge.log` for HTTP errors or authentication issues.
  - The agent will automatically downgrade to `ultra_low` profile to conserve resources.
- **High CPU Load / Thermal Throttling:**
  - Ensure ONNX Runtime is enabled (`yolov8n.onnx` present).
  - The adaptive controller will downgrade resolution from 640px to 480px or 320px automatically if CPU $> 85\%$.
- **Thumbnails Missing:**
  - Thumbnails are only produced when attendance mismatches or infrastructure deficits are detected locally.
  - In `ultra_low` mode or when daily upload byte budget is exceeded, thumbnails are disabled to preserve bandwidth.
