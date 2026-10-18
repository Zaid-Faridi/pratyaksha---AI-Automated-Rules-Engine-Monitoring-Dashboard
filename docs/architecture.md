# Pratyaksha System Architecture

This document outlines the end-to-end multi-tier architecture of **Pratyaksha**, encompassing the local edge detection runtime, offline-first sync workers, central FastAPI rules engine, and the React monitoring dashboard.

---

## 1. System Overview

Pratyaksha divides compute responsibilities cleanly between the edge and the cloud:
- **At the Edge (Skilling Centres):** Autonomous, low-bandwidth edge agents process local CCTV RTSP feeds, perform real-time object detection and ground-plane zone filtering, buffer events into a crash-safe local SQLite WAL outbox, and push ultra-compact compressed JSON metadata to the cloud.
- **In the Central Monitoring Unit (MSDE Cloud / State Data Centre):** A high-performance FastAPI backend ingests events, executes the automated compliance rules engine, reconciles claimed physical attendance registers against video evidence, tracks sanctioned inventories, monitors camera health, and serves real-time analytics to the React dashboard.

---

## 2. High-Level Architecture Diagram

```mermaid
graph TB
    subgraph SkillingCentre["Skilling Centre (Edge Layer)"]
        Camera[CCTV IP Camera / RTSP] -->|Video Stream| EdgeAgent[Edge Agent Service: agent.py]
        
        subgraph LocalEdge["Edge Processing Unit (Raspberry Pi / Mini PC)"]
            EdgeAgent --> Detector[ONNX Runtime / YOLO Detector]
            Detector --> Zones[Ground-Plane Zone Filter]
            Zones --> PreChecks[Schedule & Inventory Cache]
            PreChecks --> Outbox[(Local SQLite Outbox: WAL Mode)]
            
            Adaptive[Adaptive Controller: CPU / Queue Monitor] -.->|Adjust Profile| Detector
            Evidence[Privacy Evidence Generator] -.->|Blurred Thumbnails| Outbox
            
            Outbox --> SyncWorker[Sync Worker: sync_worker.py]
        end
    end

    subgraph CloudInfrastructure["Central Monitoring Unit (Cloud / Data Centre)"]
        SyncWorker -->|HTTPS / TLS 1.3<br/>Gzip Payload < 2KB<br/>X-API-Key| Gateway[FastAPI Ingestion Gateway]
        
        Gateway --> RulesEngine[Automated Rules Engine]
        RulesEngine --> AttendanceRule[Attendance Discrepancy Rule<br/>Threshold: 70%, K=3]
        RulesEngine --> InfraRule[Sanctioned Inventory Rule<br/>Deficit / Surplus Check]
        RulesEngine --> CameraRule[Camera Health & Tamper Rule<br/>Heartbeat: 15m, Tamper: 80%]
        
        RulesEngine --> Database[(PostgreSQL / SQLite Database)]
        Database --> RestAPI[REST API Routers: Centres, Cameras, Alerts, Dashboard]
    end

    subgraph FrontendDashboard["Central Monitoring Unit (Frontend UI)"]
        RestAPI -->|REST API & TanStack Query| ReactApp[React + TypeScript Dashboard]
        
        ReactApp --> OverviewPage[National KPI & Trends View]
        ReactApp --> MapPage[Interactive Leaflet Geo-Map]
        ReactApp --> AlertsPage[Real-Time Alert Triage Drawer]
        ReactApp --> CentreDetailPage[Centre Auditing & Inventory View]
        ReactApp --> Officer[Scheme Monitoring Officer]
    end
```

---

## 3. End-to-End Sequence Diagram (Sample to Alert to Review Flow)

The following sequence illustrates how a single frame sampled from an edge camera feed triggers an automated attendance violation alert and guides an officer through administrative review:

```mermaid
sequenceDiagram
    autonumber
    actor Officer as Scheme Monitoring Officer
    participant Cam as CCTV Camera
    participant Edge as Pratyaksha Edge Agent
    participant Outbox as Local SQLite Outbox
    participant Backend as FastAPI Rules Engine
    participant DB as Central Database
    participant UI as React Monitoring Dashboard

    %% Phase 1: Local Detection & Outbox Buffering
    Cam->>Edge: Capture raw video frame
    Edge->>Edge: Check active batch timetable (Schedule Cache)
    Edge->>Edge: Run ONNX detection (imgsz: 640px/480px/320px)
    Edge->>Edge: Count persons & items per zone
    Edge->>Edge: Discard raw frame from RAM (Privacy by Design)
    
    opt Alert condition detected locally (Discrepancy)
        Edge->>Edge: Downscale (<=320px) & apply Gaussian blur (k=35)
    end
    
    Edge->>Outbox: Atomically write event with UUID (event_id)
    
    %% Phase 2: Offline-First Synchronization
    loop Every sync interval (e.g. 5s)
        Outbox->>Backend: POST /events (Gzip-compressed batch, X-API-Key)
        Backend->>Backend: Check UUID idempotency (skip duplicates)
        Backend->>DB: Store DetectionEvent & update Camera last_seen_at
        
        %% Phase 3: Rules Engine Execution
        Backend->>Backend: Compare rolling median against claimed attendance register
        alt Smoothed attendance < 70% of claimed for 3 consecutive samples
            Backend->>DB: Insert Alert (Type: ATTENDANCE_MISMATCH, Severity: HIGH)
        end
        Backend-->>Outbox: HTTP 201 Created
        Outbox->>Outbox: Mark events as SENT in local SQLite
    end

    %% Phase 4: Officer Triage & Review
    Officer->>UI: Open Dashboard Overview & Alert Queue
    UI->>Backend: GET /alerts?status=open
    Backend->>DB: Query open alerts
    DB-->>Backend: Return alerts list
    Backend-->>UI: Return alert payload with pre-blurred thumbnail path
    UI-->>Officer: Display alert in triage drawer with blurred evidence
    Officer->>UI: Submit Review ("Verified: Discrepancy confirmed against physical register")
    UI->>Backend: PATCH /alerts/{id} (status: "verified", reviewer_notes)
    Backend->>DB: Update Alert status & trigger Compliance Score recalculation
    Backend-->>UI: Return updated alert & recalculated score
    UI-->>Officer: Show confirmation badge & updated centre compliance
```

---

## 4. Key Subsystem Responsibilities

### Edge Agent Subsystem (`/edge`)
- **`agent.py`:** Manages the main resilient capture loop, camera reconnects, and graceful shutdown.
- **`outbox.py`:** Thread-safe SQLite queue utilizing Write-Ahead Logging (WAL) and synchronous normal mode for maximum crash safety.
- **`adaptive.py`:** Background resource sentinel that samples CPU and queue depth via `psutil`, dynamically throttling profiles between `normal`, `low`, and `ultra_low`.
- **`detector_runtime.py`:** Wrapper providing CPU execution provider support with ONNX Runtime alongside native Ultralytics YOLO.
- **`evidence.py`:** Enforces strict privacy guarantees on all diagnostic thumbnail exports.

### Central Backend Subsystem (`/backend`)
- **`app/main.py`:** FastAPI service bootstrap with CORS middleware and OpenAPI specifications.
- **`app/rules_engine.py`:** Deterministic compliance evaluator implementing the 70% attendance ratio, missing sanctioned inventory, camera heartbeat offline timeout (15m), and sudden tamper drop (80%).
- **`app/routers/`:** RESTful modules covering centres, cameras, batches, attendance records, alerts, and dashboard KPI summaries.

### Frontend Dashboard Subsystem (`/frontend`)
- **React 18 + Vite + TypeScript:** High-performance single-page web app.
- **TanStack Query:** Provides optimistic updates, caching, and auto-refetching.
- **Leaflet + OpenStreetMap:** Geographic mapping of skilling centres color-coded by compliance rating.
- **Recharts:** Interactive multi-series trends and alert category breakdowns.
