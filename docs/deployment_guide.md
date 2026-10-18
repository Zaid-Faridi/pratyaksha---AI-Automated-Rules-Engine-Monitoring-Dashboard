# Pratyaksha Field Deployment & Scaling Guide

This guide provides technical specifications, setup workflows, and architectural guidance for deploying Pratyaksha across rural and urban government skilling centres under the Ministry of Skill Development and Entrepreneurship (MSDE).

---

## 1. Hardware Selection Matrix

| Tier | Recommended Hardware | Compute Specs | Target Environment | Unit Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Budget Edge** | **Raspberry Pi 4 Model B** | Broadcom BCM2711, 4-core Cortex-A72 @ 1.5 GHz, 2GB/4GB RAM | Remote rural ITIs; single camera feed; `low` or `ultra_low` profile | ~$45–$55 |
| **Standard Edge** | **Raspberry Pi 5** | Broadcom BCM2712, 4-core Cortex-A76 @ 2.4 GHz, 4GB RAM | Semi-urban centres; dual camera feeds; `normal` profile | ~$60–$80 |
| **Industrial / Mini PC (Recommended)** | **Intel N100 / N95 Mini PC** | 4-core Alder Lake-N up to 3.4 GHz, 8GB DDR5, 128GB NVMe SSD | High-volume multi-zone centres; 3–4 concurrent camera streams | ~$120–$150 |
| **GPU Edge** | **NVIDIA Jetson Orin Nano** | 6-core ARM Cortex-A78AE, Ampere GPU (1024 CUDA cores), 4GB/8GB RAM | Large vocational hubs with 6+ high-density workshops | ~$200–$250 |

---

## 2. Low-Bandwidth Operating Profiles

The edge agent includes three built-in profiles designed to match available network capacity:

| Parameter | `ultra_low` | `low` | `normal` |
| :--- | :---: | :---: | :---: |
| **Target Connectivity** | 2G / EDGE / Saturated Satellite (<256 Kbps) | Rural 3G / Unstable DSL (256 Kbps – 1 Mbps) | 4G/LTE / Broadband (> 2 Mbps) |
| **Sample Interval** | **60 seconds** | **30 seconds** | **15 seconds** |
| **Input Resolution** | $320 \times 320\text{ px}$ | $480 \times 480\text{ px}$ | $640 \times 640\text{ px}$ |
| **Batch Upload Size** | 20 samples | 10 samples | 5 samples |
| **Evidence Thumbnails** | **Disabled** (Metadata only) | **On Critical Deficit Only** | **Enabled** (Standard) |

---

## 3. Measured Bandwidth Consumption (From Phase 4 Simulator)

*These numbers reflect empirical measurements captured during active video stream processing:*

| Profile | Samples/Hour | Metadata Transferred | Thumbnails / Hr | Hourly Data Rate | Daily Shift (8 Hours) | Monthly (26 Days) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`ultra_low`** | 60 | 894 Bytes (0.9 KB) | 0 (None) | **0.9 KB / hr** | **0.01 MB / day** | **0.26 MB / month** |
| **`low`** | 120 | 3.3 KB | 2 / hr (Critical only) | **14.6 KB / hr** | **0.11 MB / day** | **2.86 MB / month** |
| **`normal`** | 240 | 12.5 KB | 6 / hr (Standard) | **46.3 KB / hr** | **0.36 MB / day** | **9.36 MB / month** |

> [!TIP]
> Under `ultra_low` mode, an entire month of automated continuous monitoring across an 8-hour workday consumes **less than 1 megabyte of data**, allowing deployment on the most bandwidth-deprived rural telecom towers.

---

## 4. Edge Agent Installation

### Option A: Systemd Field Service (Production on Mini PC / Raspberry Pi)

```bash
# 1. Clone repository to /opt
sudo git clone https://github.com/Zaid-Faridi/pratyaksha---AI-Automated-Rules-Engine-Monitoring-Dashboard.git /opt/pratyaksha
cd /opt/pratyaksha

# 2. Set up virtual environment and dependencies
sudo python3 -m venv .venv
sudo /opt/pratyaksha/.venv/bin/pip install --upgrade pip
sudo /opt/pratyaksha/.venv/bin/pip install -r edge/requirements.txt

# 3. Export ONNX model for CPU acceleration
sudo /opt/pratyaksha/.venv/bin/python edge/export_onnx.py --model yolov8n.pt --output yolov8n.onnx

# 4. Create system user and configuration directories
sudo useradd -r -s /bin/false pratyaksha || true
sudo mkdir -p /etc/pratyaksha /var/lib/pratyaksha/data /var/log/pratyaksha
sudo chown -R pratyaksha:pratyaksha /var/lib/pratyaksha /var/log/pratyaksha /opt/pratyaksha

# 5. Copy environment file and systemd unit
sudo cp edge/edge_config.yaml /etc/pratyaksha/
sudo cp edge/pratyaksha-edge.service /etc/systemd/system/

# 6. Enable and start daemon
sudo systemctl daemon-reload
sudo systemctl enable pratyaksha-edge
sudo systemctl start pratyaksha-edge
sudo systemctl status pratyaksha-edge
```

### Option B: Docker Container Deployment

```bash
# In the project directory
docker compose -f edge/docker-compose.yml up -d
docker compose -f edge/docker-compose.yml logs -f
```

---

## 5. Central Backend Setup

```bash
# 1. Navigate to backend directory
cd backend

# 2. Configure environment (PostgreSQL or SQLite)
export DATABASE_URL="postgresql://user:password@localhost:5432/pratyaksha"  # Optional
export EDGE_API_KEY="your-secure-shared-key"

# 3. Initialize database tables
python -c "from app.database import init_db; init_db()"

# 4. Seed initial centres, cameras, batches, and inventory
python scripts/seed.py

# 5. Start Uvicorn production server
uvicorn app.main:app --host 0.0.0.0 --port 8088 --workers 4
```

---

## 6. Scaling to Thousands of Training Centres

Scaling Pratyaksha nationwide across 15,000+ government skilling centres requires addressing database write concurrency, network spikes after power restoration, and centralized indexing:

### 1. Database Indexing & Partitioning
- **Primary Indexes:** B-Tree indexing on `detection_events(camera_id, timestamp)` and `detection_events(event_id)`.
- **Table Partitioning:** In PostgreSQL, range-partition `detection_events` by month (e.g. `detection_events_2026_10`). Older monthly partitions can be automatically detached and compressed into cold storage after 90 days.

### 2. Thundering Herd Mitigation after Regional Power Restoration
- When an entire district experiences a grid power outage followed by restoration, hundreds of edge devices simultaneously reconnect and attempt to drain their local outboxes.
- **Jittered Sync Intervals:** The edge sync worker applies randomized jitter ($\pm 20\%$) to `sync_interval_sec` to scatter arrival timestamps.
- **Batch Ingestion:** Instead of individual HTTP requests per frame, the edge agent bundles up to 20 events into a single compressed HTTP POST.

### 3. Message Queue Ingestion Architecture (Enterprise Tier)
- For scale beyond 5,000 centres, replace direct HTTP-to-SQL ingestion with a lightweight message broker:
  - **Edge Agent** $\rightarrow$ **API Gateway** $\rightarrow$ **Kafka / Redis Streams** $\rightarrow$ **Worker Pool** $\rightarrow$ **PostgreSQL**.
  - This guarantees that API gateway response latency remains under $10\text{ ms}$ regardless of backend database write load.

### 4. Regional Edge Aggregators
- In large states (e.g. Uttar Pradesh, Maharashtra), a lightweight regional edge aggregator can be deployed at the State Data Centre (SDC) to aggregate district-level feeds before syncing high-level KPIs to the central MSDE national dashboard.
