#!/usr/bin/env python3
"""
Phase 1 JSONL to Phase 2 Backend Adapter.
Reads detection events from Phase 1 output JSONL and streams them to the FastAPI /events endpoint.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import httpx


def ingest_jsonl(file_path: str, api_url: str, batch_size: int = 50) -> None:
    path = Path(file_path)
    if not path.is_file():
        print(f"[ERROR] JSONL file not found at '{file_path}'", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Reading Phase 1 detections from: {path}")
    print(f"[INFO] Target API endpoint: {api_url}")

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                records.append(data)
            except json.JSONDecodeError as e:
                print(f"[WARNING] Skipping invalid JSON line {line_num}: {e}")

    total_records = len(records)
    print(f"[INFO] Parsed {total_records} valid detection events.")
    if total_records == 0:
        print("[INFO] No records to transmit.")
        return

    # Transmit in batches
    success_count = 0
    with httpx.Client(timeout=30.0) as client:
        for i in range(0, total_records, batch_size):
            chunk = records[i : i + batch_size]
            try:
                response = client.post(api_url, json=chunk)
                if response.status_code == 201:
                    res_data = response.json()
                    ingested = res_data.get("events_ingested", len(chunk))
                    success_count += ingested
                    alerts = res_data.get("alerts_evaluated", 0)
                    print(f"  • Batch {i // batch_size + 1}: Ingested {ingested} events | Alerts evaluated: {alerts}")
                else:
                    print(f"[ERROR] Failed batch {i // batch_size + 1}: HTTP {response.status_code} - {response.text}")
            except Exception as e:
                print(f"[ERROR] Connection failed connecting to {api_url}: {e}")
                print("[TIP] Ensure the FastAPI backend server is running: 'uvicorn app.main:app --port 8000'")
                sys.exit(1)

    print(f"\n[COMPLETE] Successfully transmitted {success_count}/{total_records} detection events.")


def main():
    parser = argparse.ArgumentParser(description="Pratyaksha Phase 1 JSONL to Phase 2 Backend Ingestion Adapter")
    parser.add_argument(
        "--file",
        type=str,
        default="../outputs/detections.jsonl",
        help="Path to Phase 1 JSON Lines output file.",
    )
    default_api = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/") + "/events"
    parser.add_argument(
        "--url",
        type=str,
        default=default_api,
        help="FastAPI /events endpoint URL.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of detection events to submit per HTTP batch request.",
    )
    args = parser.parse_args()

    ingest_jsonl(file_path=args.file, api_url=args.url, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
