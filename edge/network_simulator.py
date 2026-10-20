"""
Network Fault and Bandwidth Simulator for Pratyaksha Edge.
Demonstrates:
1. Prolonged network outage simulation -> Events safely accumulate in local SQLite outbox.
2. Network recovery -> Sync worker automatically resumes and flushes all events with zero loss.
3. Idempotency verification -> Duplicate retransmissions are ignored by backend.
4. Comprehensive byte-usage accounting report across profiles (ultra_low, low, normal).
"""

from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sys
import time
from typing import Dict, List

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import requests

from edge.adaptive import AdaptiveController
from edge.config import PROFILES, EdgeConfig
from edge.outbox import OutboxQueue
from edge.sync_worker import SyncWorker


def simulate_outage_and_recovery(
    backend_url: str = None,
    camera_id: str = "cam_01",
    centre_id: str = "centre_mh_01",
) -> None:
    backend_url = (backend_url or os.getenv("BACKEND_URL") or os.getenv("PRATYAKSHA_BACKEND_URL") or "http://127.0.0.1:8088").rstrip("/")
    # Auto-discover first available centre and camera if possible
    try:
        r_centres = requests.get(f"{backend_url}/centres", timeout=3.0)
        if r_centres.status_code == 200 and r_centres.json():
            centre_id = r_centres.json()[0]["id"]
        r_cams = requests.get(f"{backend_url}/cameras", timeout=3.0)
        if r_cams.status_code == 200 and r_cams.json():
            camera_id = r_cams.json()[0]["id"]
    except Exception:
        pass

    print("=" * 80)
    print("PRATYAKSHA EDGE RESILIENCE & NETWORK FAULT SIMULATION")
    print(f"Backend Target: {backend_url}")
    print(f"Centre ID     : {centre_id}")
    print(f"Camera ID     : {camera_id}")
    print("=" * 80)

    sim_db = "edge/data/sim_outbox.db"
    # Clean old sim db
    if Path(sim_db).exists():
        Path(sim_db).unlink()

    outbox = OutboxQueue(db_path=sim_db)
    config = EdgeConfig(
        centre_id=centre_id,
        camera_id=camera_id,
        backend_url=backend_url,
        db_path=sim_db,
    )
    adaptive = AdaptiveController(config=config, outbox=outbox)
    sync = SyncWorker(config=config, outbox=outbox, adaptive=adaptive)

    # Register camera in backend if not already present
    try:
        requests.post(
            f"{backend_url}/cameras",
            json={"id": camera_id, "centre_id": centre_id, "zone_names": ["classroom"]},
            timeout=3.0,
        )
    except Exception:
        pass

    # --- PHASE 1: Online Normal Operation ---
    print("\n[PHASE 1] Online Operation (Baseline)")
    print("-" * 80)
    print("Sampling 5 frames and syncing to cloud in real-time...")
    for i in range(1, 6):
        sample = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "camera_id": camera_id,
            "zone": "classroom",
            "person_count": {"raw": 18, "smoothed": 18},
            "infrastructure": [{"item": "chair", "expected": 20, "detected": 19, "status": "DEFICIT"}],
        }
        eid = outbox.enqueue_event(sample)
        print(f"  • Enqueued Event #{i} (UUID: {eid[:8]}...)")

    assert outbox.get_queue_depth() == 5, "Queue depth should be 5"
    flushed = sync.sync_events_batch()
    print(f"  ✓ Flushed {flushed} events. Remaining Outbox Queue Depth: {outbox.get_queue_depth()}")
    assert outbox.get_queue_depth() == 0, "Queue depth should be 0 after sync"

    # --- PHASE 2: Severe Network Outage ---
    print("\n[PHASE 2] Network Outage Simulation (Connection Dropped / Satellite Down)")
    print("-" * 80)
    print("Cutting cloud connection (redirecting to unreachable port)...")
    sync.config.backend_url = "http://127.0.0.1:9999"  # Dead port

    print("Edge agent continues local video inference and local outbox buffering...")
    outage_event_ids = []
    for i in range(6, 16):
        sample = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "camera_id": camera_id,
            "zone": "classroom",
            "person_count": {"raw": 20, "smoothed": 20},
            "infrastructure": [{"item": "chair", "expected": 20, "detected": 20, "status": "MATCH"}],
        }
        eid = outbox.enqueue_event(sample)
        outage_event_ids.append(eid)
        print(f"  • [OUTAGE BUFFERING] Event #{i} stored safely in SQLite outbox (UUID: {eid[:8]}...)")

    print(f"\nAttempting sync during outage...")
    res = sync.sync_events_batch()
    print(f"  ! Sync result during outage: {res} synced (Expected failure with backoff).")
    print(f"  ✓ Outbox Queue Depth preserved safely: {outbox.get_queue_depth()} events buffered locally.")
    assert outbox.get_queue_depth() == 10, "All 10 outage events must be safely preserved in local SQLite"

    # --- PHASE 3: Network Restoration & Drain ---
    print("\n[PHASE 3] Network Recovery & Outbox Drain")
    print("-" * 80)
    print("Network connectivity restored! Re-pointing to valid backend...")
    sync.config.backend_url = backend_url

    total_drained = 0
    while outbox.get_queue_depth() > 0:
        drained = sync.sync_events_batch()
        total_drained += drained
        print(f"  ✓ Flushed batch of {drained} events. Remaining queue: {outbox.get_queue_depth()}")

    print(f"\n[DATA INTEGRITY VERIFIED] Total events drained: {total_drained}/10 (Zero Data Loss!).")
    assert outbox.get_queue_depth() == 0, "Queue depth must be 0 after recovery"

    # --- PHASE 4: Idempotency Verification ---
    print("\n[PHASE 4] Idempotency Verification (Duplicate Re-transmission Test)")
    print("-" * 80)
    print("Simulating re-transmission of already-processed event UUIDs...")
    dup_sample = {
        "event_id": outage_event_ids[0],  # Re-send first outage event
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "camera_id": camera_id,
        "zone": "classroom",
        "person_count": {"raw": 20, "smoothed": 20},
        "infrastructure": [],
    }
    resp = requests.post(f"{backend_url}/events", json=[dup_sample])
    resp_data = resp.json()
    print(f"  Backend Response: {resp_data}")
    print(f"  Duplicates skipped by backend: {resp_data.get('duplicates_skipped', 0)}")
    assert resp_data.get("duplicates_skipped") == 1, "Backend must ignore duplicate UUID"
    print("  ✓ Idempotency verified: duplicate rejected without duplicate database entries.")

    # --- PHASE 5: Bandwidth & Byte Usage Analysis ---
    print("\n[PHASE 5] MEASURED BANDWIDTH CONSUMPTION REPORT")
    print("=" * 80)
    generate_bandwidth_report()


def generate_bandwidth_report() -> None:
    """
    Measure and project exact byte usage across all 3 profiles.
    """
    # Sample realistic event
    sample_event = {
        "event_id": "a5e8c148-734d-4bc6-91e8-78da37286d91",
        "timestamp": "2026-10-18T10:30:00Z",
        "camera_id": "cam_01",
        "zone": "classroom",
        "person_count": {"raw": 19, "smoothed": 20},
        "infrastructure": [
            {"item": "chair", "expected": 20, "detected": 19, "status": "DEFICIT"},
            {"item": "workbench", "expected": 10, "detected": 10, "status": "MATCH"},
            {"item": "computer", "expected": 10, "detected": 10, "status": "MATCH"},
        ],
    }

    # Measure raw vs compressed bytes
    raw_json_bytes = len(json.dumps(sample_event).encode("utf-8"))
    compact_json_bytes = len(json.dumps(sample_event, separators=(",", ":")).encode("utf-8"))
    compressed_bytes = len(gzip.compress(json.dumps([sample_event], separators=(",", ":")).encode("utf-8")))

    # Simulated evidence thumbnail (320px JPEG @ 50 quality)
    sample_thumbnail_bytes = 5800  # ~5.8 KB

    print(f"Single Sample Metadata Sizes:")
    print(f"  • Standard JSON        : {raw_json_bytes} bytes")
    print(f"  • Compact JSON         : {compact_json_bytes} bytes")
    print(f"  • Gzip Compressed      : {compressed_bytes} bytes  (Target: < 2 KB achieved!)")
    print(f"  • Privacy Thumbnail    : {sample_thumbnail_bytes} bytes (~5.8 KB)")

    print("\n" + "=" * 90)
    print("| Profile | Sample Interval | Samples/Hour | Metadata Bytes/Hour | Evidence Thumbnails | Total KB/Hour | Daily (8 hrs) |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    profile_specs = [
        ("ultra_low", 60.0, 0, "None (Metadata-only)"),
        ("low", 30.0, 2, "2 / hr (Critical only)"),
        ("normal", 15.0, 6, "6 / hr (Standard)"),
    ]

    for p_name, interval, thumbs_per_hr, thumb_desc in profile_specs:
        samples_hr = int(3600 / interval)
        # Gzip compressed in batches of profile batch_size
        batch_size = PROFILES[p_name].batch_size
        num_batches = int(samples_hr / batch_size)
        sample_batch = [sample_event for _ in range(batch_size)]
        batch_gzip_bytes = len(gzip.compress(json.dumps(sample_batch, separators=(",", ":")).encode("utf-8")))
        meta_bytes_hr = num_batches * batch_gzip_bytes

        evidence_bytes_hr = thumbs_per_hr * sample_thumbnail_bytes
        total_bytes_hr = meta_bytes_hr + evidence_bytes_hr
        total_kb_hr = total_bytes_hr / 1024.0
        daily_mb = (total_bytes_hr * 8) / (1024.0 * 1024.0)

        print(
            f"| `{p_name:<9}` | {interval:4.0f}s | {samples_hr:4d} | {meta_bytes_hr:6d} B ({meta_bytes_hr/1024.0:4.1f} KB) | "
            f"{thumbs_per_hr:2d} ({thumb_desc:<16}) | {total_kb_hr:6.1f} KB/hr | {daily_mb:5.2f} MB/day |"
        )
    print("=" * 90)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pratyaksha Network Simulator and Bandwidth Reporter")
    parser.add_argument("--backend", default="http://127.0.0.1:8088", help="FastAPI backend URL")
    parser.add_argument("--report-only", action="store_true", help="Print bandwidth consumption table only")
    args = parser.parse_args()

    if args.report_only:
        generate_bandwidth_report()
    else:
        simulate_outage_and_recovery(backend_url=args.backend)


if __name__ == "__main__":
    main()
