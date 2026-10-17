"""
Background Sync Worker for Pratyaksha Edge.
Uploads queued events in compact gzip-compressed batches, delivers lazy evidence thumbnails,
maintains heartbeats with telemetry, and applies exponential backoff on network failures.
"""

from datetime import datetime, timezone
import gzip
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional
import requests

from edge.adaptive import AdaptiveController
from edge.config import EdgeConfig
from edge.evidence import EvidenceGenerator
from edge.outbox import OutboxQueue


logger = logging.getLogger("pratyaksha.sync")


class SyncWorker:
    """
    Manages cloud synchronization for the edge agent.
    """
    def __init__(
        self,
        config: EdgeConfig,
        outbox: OutboxQueue,
        adaptive: AdaptiveController,
    ) -> None:
        self.config = config
        self.outbox = outbox
        self.adaptive = adaptive

        self.running = False
        self._thread: Optional[threading.Thread] = None

        # Network backoff state
        self.current_backoff_sec = 1.0
        self.max_backoff_sec = 60.0
        self.last_heartbeat_time = 0.0
        self.last_sample_time_iso: Optional[str] = None

    def _get_headers(self, is_gzip: bool = False) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if is_gzip:
            headers["Content-Encoding"] = "gzip"
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        return headers

    def sync_events_batch(self) -> int:
        """
        Upload one batch of pending detection events.
        Gzip-compresses payload to minimize data transfer (<2 KB per sample).
        Returns number of events successfully synchronized.
        """
        batch_size = self.adaptive.current_profile.batch_size
        pending = self.outbox.get_pending_events(limit=batch_size)
        if not pending:
            return 0

        event_ids = [e["event_id"] for e in pending]

        # Clean payload for backend schema
        clean_events = []
        for e in pending:
            clean = {k: v for k, v in e.items() if not k.startswith("_")}
            clean_events.append(clean)

        # Gzip compression for minimal payload footprint
        raw_json = json.dumps(clean_events, separators=(",", ":")).encode("utf-8")
        compressed_payload = gzip.compress(raw_json)
        transferred_bytes = len(compressed_payload)

        url = f"{self.config.backend_url}/events"
        headers = self._get_headers(is_gzip=True)

        try:
            resp = requests.post(
                url,
                data=compressed_payload,
                headers=headers,
                timeout=self.config.request_timeout_sec,
            )

            if 200 <= resp.status_code < 300:
                self.outbox.mark_events_sent(event_ids, transferred_bytes=transferred_bytes)
                self.current_backoff_sec = 1.0  # Reset backoff on success
                logger.info(
                    f"[SYNC SUCCESS] Flushed {len(clean_events)} events ({transferred_bytes} bytes, compressed). "
                    f"Queue depth: {self.outbox.get_queue_depth()}"
                )
                return len(clean_events)
            else:
                err_msg = f"HTTP {resp.status_code}: {resp.text[:120]}"
                self.outbox.mark_events_failed(event_ids, err_msg)
                logger.warning(f"[SYNC ERROR] {err_msg}")
                self._apply_backoff()
                return 0
        except Exception as exc:
            err_msg = f"Network failure: {str(exc)}"
            self.outbox.mark_events_failed(event_ids, err_msg)
            logger.warning(f"[SYNC OFFLINE] {err_msg}. Retrying in {self.current_backoff_sec:.1f}s")
            self._apply_backoff()
            return 0

    def sync_evidence_lazy(self) -> bool:
        """
        Lazily upload one pending evidence thumbnail if bandwidth and daily budget allow.
        """
        # 1. Byte budget check
        if self.outbox.is_budget_exceeded(self.config.daily_budget_bytes):
            pending = self.outbox.get_pending_evidence(limit=5)
            for item in pending:
                self.outbox.mark_evidence_skipped(item["id"])
            logger.warning("[EVIDENCE BUDGET] Daily upload budget exceeded. Dropping thumbnails to preserve bandwidth.")
            return False

        # 2. Fetch pending thumbnail
        pending_items = self.outbox.get_pending_evidence(limit=1)
        if not pending_items:
            return False

        item = pending_items[0]
        ev_id = item["id"]
        event_id = item["event_id"]
        file_path = item["file_path"]

        b64_data = EvidenceGenerator.to_base64(file_path)
        if not b64_data:
            self.outbox.mark_evidence_skipped(ev_id)
            return False

        url = f"{self.config.backend_url}/events/evidence"
        headers = self._get_headers(is_gzip=False)
        payload = {
            "event_id": event_id,
            "camera_id": item["camera_id"],
            "image_b64": b64_data,
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.config.request_timeout_sec,
            )
            if 200 <= resp.status_code < 300:
                self.outbox.mark_evidence_sent(ev_id, byte_size=item["byte_size"])
                logger.info(f"[EVIDENCE UPLOADED] Event {event_id} ({item['byte_size']} bytes)")
                return True
            else:
                return False
        except Exception:
            return False

    def send_heartbeat(self, force: bool = False) -> bool:
        """
        Send camera heartbeat with edge hardware telemetry.
        """
        now = time.time()
        if not force and (now - self.last_heartbeat_time < self.config.heartbeat_interval_sec):
            return False

        metrics = self.adaptive.get_system_metrics()
        url = f"{self.config.backend_url}/cameras/{self.config.camera_id}/heartbeat"
        headers = self._get_headers(is_gzip=False)

        payload = {
            "queue_depth": metrics["queue_depth"],
            "last_sample_time": self.last_sample_time_iso or datetime.now(timezone.utc).isoformat(),
            "cpu_percent": metrics["cpu_percent"],
            "memory_percent": metrics["memory_percent"],
            "agent_version": "1.0.0",
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.config.request_timeout_sec)
            if resp.status_code == 200:
                self.last_heartbeat_time = now
                data = resp.json()
                logger.debug(f"[HEARTBEAT OK] Camera {self.config.camera_id} online, agent health: {data.get('agent_health')}")
                return True
            return False
        except Exception as exc:
            logger.debug(f"[HEARTBEAT FAILED] {exc}")
            return False

    def _apply_backoff(self) -> None:
        time.sleep(self.current_backoff_sec)
        self.current_backoff_sec = min(self.max_backoff_sec, self.current_backoff_sec * 2.0)

    def run_loop(self) -> None:
        """
        Continuous worker loop for background execution.
        """
        logger.info("[SYNC WORKER] Background sync service started.")
        while self.running:
            try:
                # 1. Sync events batch
                sent_count = self.sync_events_batch()

                # 2. If healthy and queue is clearing, sync pending evidence
                if sent_count > 0 or self.outbox.get_queue_depth() == 0:
                    self.sync_evidence_lazy()

                # 3. Heartbeat check
                self.send_heartbeat()

                # 4. Sleep interval
                time.sleep(self.config.sync_interval_sec)
            except Exception as e:
                logger.error(f"[SYNC WORKER ERROR] {e}")
                time.sleep(self.config.sync_interval_sec)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.running = True
        self._thread = threading.Thread(target=self.run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=3.0)
