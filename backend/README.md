# Pratyaksha (प्रत्यक्ष) - Phase 2: Backend & Rules Engine
> **FastAPI Compliance Auditor & Analytics Backend for Skilling Centres**  
> *MSDE Problem Statement 26245*

The Phase 2 backend ingests video detection events from Phase 1 edge agents, maintains the master inventory & schedule registries, evaluates automated compliance rules, and generates actionable alerts for administrative oversight.

---

## Key Features & Architecture

1. **High-Performance Event Ingestion**:
   - Ingests single or batch events directly matching the Phase 1 detection format (`timestamp`, `camera_id`, `zone`, `person_count: {raw, smoothed}`, `infrastructure`).
   - Updates camera `last_seen_at` and triggers rules evaluation on arrival.

2. **Automated Rules Engine (`app/rules_engine.py`)**:
   - **Attendance Mismatch**: Compares actual observed median attendance against officially claimed attendance during active batch windows. Flags shortfalls < 70% over $N=3$ consecutive windows, scaling severity (MEDIUM, HIGH, CRITICAL) by the deficit.
   - **Infrastructure Gap & Surplus**: Flags missing equipment after $M=3$ consecutive deficient samples (`INFRASTRUCTURE_GAP`). Flags extra equipment as informational (`INFRASTRUCTURE_SURPLUS`).
   - **Camera Tamper & Offline Health**: Flags cameras silent for > 15 minutes during scheduled classes (`CAMERA_OFFLINE`), and flags sudden object drops $\ge 80\%$ (`CAMERA_TAMPER`).
   - **Schedule Awareness**: Automatically respects batch timetables and non-batch days, suppressing false alerts when classrooms are closed.
   - **De-duplication & Auto-Resolution**: Prevents duplicate open alerts and automatically resolves alerts (`status = "auto_resolved"`) once attendance or equipment recovers.
   - **Weighted Compliance Scoring (0–100)**: Evaluates each centre on:
     $$\text{Compliance Score} = 100 \times (0.45 \times \text{Attendance Rate} + 0.35 \times \text{Infra Rate} + 0.20 \times \text{Camera Uptime})$$

3. **Privacy by Design**:
   - Stores only aggregate counts and operational metadata.
   - Zero facial identification or biometric storage.
   - Optional evidence thumbnails must be pre-blurred by edge agents.
   - Configurable automated data retention policy (`cleanup_old_events`).

4. **Multi-Database Support**:
   - Default: SQLite (`sqlite:///./pratyaksha.db`) for zero-configuration local development.
   - Production: PostgreSQL switchable via `DATABASE_URL` environment variable.

---

## Directory Structure

```
backend/
├── app/
│   ├── config.py              # Settings via Pydantic & rules thresholds
│   ├── database.py            # SQLAlchemy engine, session maker, Base, init_db
│   ├── models.py              # ORM models (Centre, Camera, Batch, Inventory, Attendance, Event, Alert)
│   ├── schemas.py             # Pydantic v2 validation models & Phase 1 JSONL ingestion schema
│   ├── rules_engine.py        # Compliance rules, deduplication, auto-resolution, and scoring
│   ├── routers/
│   │   ├── events.py          # POST /events (single & batch)
│   │   ├── attendance.py      # POST /attendance (claimed attendance submissions)
│   │   ├── centres.py         # CRUD /centres and GET /centres/{id}/compliance
│   │   ├── cameras.py         # CRUD /cameras and POST /cameras/{id}/heartbeat
│   │   ├── inventory.py       # CRUD /inventory
│   │   ├── batches.py         # CRUD /batches
│   │   ├── alerts.py          # GET /alerts (filters) and PATCH /alerts/{id} (verify/dismiss)
│   │   └── dashboard.py       # GET /dashboard/summary
│   └── main.py                # FastAPI app initialization, CORS, OpenAPI docs
├── scripts/
│   ├── seed.py                # Seeds 5 diverse centres, inventory, batches, and 3 days of events
│   └── ingest_phase1_jsonl.py # Adapter script reading Phase 1 JSONL output into /events
├── tests/
│   ├── conftest.py            # SQLite in-memory test fixtures and FastAPI test client
│   ├── test_rules.py          # Unit tests for all rules engine requirements & edge cases
│   └── test_api.py            # Integration tests for all REST API endpoints
├── requirements.txt           # Python dependencies (FastAPI, SQLAlchemy, Pydantic, pytest)
└── README.md                  # Phase 2 documentation
```

---

## Setup & Execution

### 1. Environment Setup

```bash
# Navigate to the backend directory
cd backend

# Use existing root virtualenv or create a dedicated one:
source ../.venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Seed Database with Demonstration Data

Seeds 5 centres across Maharashtra, Uttar Pradesh, Karnataka, Odisha, and Rajasthan, complete with cameras, inventory baselines, scheduled batches, claimed attendance, and 3 days of simulated events with realistic compliance violations:

```bash
python scripts/seed.py
```

### 3. Start the FastAPI Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### 4. Run the Test Suite

Run the full pytest suite covering edge cases (occlusion dips, batch boundaries, duplicate alerts, auto-resolution, and API flows):

```bash
PYTHONPATH=. pytest -v
```

---

## Ingesting Phase 1 Detections

Stream detection events generated by the Phase 1 pipeline (`outputs/detections.jsonl`) directly to the backend:

```bash
python scripts/ingest_phase1_jsonl.py --file ../outputs/detections.jsonl --url http://localhost:8000/events
```

---

## Sample cURL Commands

### 1. Ingest Detection Event (Phase 1 JSONL Format)
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-10-19T10:00:00Z",
    "camera_id": "cam_mh_01",
    "zone": "classroom",
    "person_count": {
      "raw": 19,
      "smoothed": 19
    },
    "infrastructure": [
      {"item": "chair", "expected": 20, "detected": 20, "status": "MATCH"},
      {"item": "computer", "expected": 10, "detected": 10, "status": "MATCH"}
    ]
  }'
```

### 2. Submit Claimed Attendance
```bash
curl -X POST http://localhost:8000/attendance \
  -H "Content-Type: application/json" \
  -d '{
    "centre_id": "centre_mh_01",
    "batch_id": "batch_pune_01",
    "date": "2026-10-19",
    "claimed_count": 20
  }'
```

### 3. Check Centre Compliance Breakdown
```bash
curl -X GET http://localhost:8000/centres/centre_mh_01/compliance
```

### 4. Fetch Dashboard Summary
```bash
curl -X GET http://localhost:8000/dashboard/summary
```

### 5. Filter Open Compliance Alerts
```bash
curl -X GET "http://localhost:8000/alerts?status=open&severity=HIGH"
```

### 6. Review / Verify an Alert
```bash
curl -X PATCH http://localhost:8000/alerts/2 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "verified",
    "reviewed_by": "Inspector Zaid",
    "review_notes": "Physical attendance register cross-checked; shortfall confirmed."
  }'
```

### 7. Camera Heartbeat
```bash
curl -X POST http://localhost:8000/cameras/cam_mh_01/heartbeat
```

---

## Sample Alert JSON Representation

```json
{
  "id": 2,
  "centre_id": "centre_up_02",
  "camera_id": "cam_up_01",
  "zone": "classroom",
  "item": null,
  "type": "ATTENDANCE_MISMATCH",
  "severity": "HIGH",
  "message": "Attendance shortfall in zone 'classroom' during batch 'Handloom & Textile Operator': median observed 8.0 vs claimed 25 (32.0% attendance over last 3 samples).",
  "evidence_thumbnail_path": null,
  "created_at": "2026-10-17T12:02:10.157650Z",
  "status": "open",
  "reviewed_by": null,
  "reviewed_at": null,
  "review_notes": null
}
```
