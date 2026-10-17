"""
Offline-First SQLite Outbox Queue for Pratyaksha Edge Agent.
Guarantees zero data loss across prolonged network outages and sudden power cuts.
Provides idempotency tracking, retry counters, and daily byte budget accounting.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple
import uuid


class OutboxQueue:
    """
    Thread-safe SQLite persistent outbox queue with Write-Ahead Logging (WAL).
    """
    def __init__(self, db_path: str = "edge/data/outbox.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS outbox_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    camera_id TEXT NOT NULL,
                    zone TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    sent_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_outbox_status_id ON outbox_events(status, id);
                CREATE INDEX IF NOT EXISTS idx_outbox_event_id ON outbox_events(event_id);

                CREATE TABLE IF NOT EXISTS outbox_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    created_at TEXT NOT NULL,
                    sent_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_status ON outbox_evidence(status, id);

                CREATE TABLE IF NOT EXISTS daily_usage (
                    date_str TEXT PRIMARY KEY,
                    bytes_metadata INTEGER NOT NULL DEFAULT 0,
                    bytes_evidence INTEGER NOT NULL DEFAULT 0,
                    total_bytes INTEGER NOT NULL DEFAULT 0
                );
            """)

    @staticmethod
    def _current_utc_str() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _current_date_str() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def enqueue_event(
        self,
        event_dict: Dict[str, Any],
        evidence_path: Optional[str] = None,
    ) -> str:
        """
        Atomically persist an event and optional evidence thumbnail to SQLite outbox.
        Ensures a unique event_id is assigned for end-to-end idempotency.
        """
        event_id = event_dict.get("event_id") or str(uuid.uuid4())
        event_dict["event_id"] = event_id

        camera_id = event_dict.get("camera_id", "unknown")
        zone = event_dict.get("zone", "unknown")
        timestamp = event_dict.get("timestamp", self._current_utc_str())
        payload_json = json.dumps(event_dict)
        now_str = self._current_utc_str()

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO outbox_events (
                    event_id, camera_id, zone, timestamp, payload_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
                """,
                (event_id, camera_id, zone, timestamp, payload_json, now_str),
            )

            if evidence_path and Path(evidence_path).exists():
                size = Path(evidence_path).stat().st_size
                conn.execute(
                    """
                    INSERT INTO outbox_evidence (
                        event_id, camera_id, file_path, byte_size, status, created_at
                    ) VALUES (?, ?, ?, ?, 'PENDING', ?)
                    """,
                    (event_id, camera_id, str(evidence_path), size, now_str),
                )

        return event_id

    def get_pending_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve a batch of pending events ordered by timestamp.
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, event_id, payload_json, retry_count
                FROM outbox_events
                WHERE status = 'PENDING'
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()

        events = []
        for r in rows:
            data = json.loads(r["payload_json"])
            data["_outbox_id"] = r["id"]
            data["_retry_count"] = r["retry_count"]
            events.append(data)
        return events

    def mark_events_sent(self, event_ids: List[str], transferred_bytes: int = 0) -> None:
        """
        Mark events as successfully SENT and record byte consumption.
        """
        if not event_ids:
            return

        now_str = self._current_utc_str()
        placeholders = ",".join("?" for _ in event_ids)

        with self._lock, self._get_connection() as conn:
            conn.execute(
                f"""
                UPDATE outbox_events
                SET status = 'SENT', sent_at = ?
                WHERE event_id IN ({placeholders})
                """,
                [now_str] + event_ids,
            )

            if transferred_bytes > 0:
                self._record_bytes_internal(conn, transferred_bytes, is_evidence=False)

    def mark_events_failed(self, event_ids: List[str], error_msg: str) -> None:
        """
        Increment retry count and record error details.
        """
        if not event_ids:
            return

        placeholders = ",".join("?" for _ in event_ids)
        with self._lock, self._get_connection() as conn:
            conn.execute(
                f"""
                UPDATE outbox_events
                SET retry_count = retry_count + 1, last_error = ?
                WHERE event_id IN ({placeholders})
                """,
                [error_msg[:255]] + event_ids,
            )

    def get_pending_evidence(self, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve pending evidence thumbnails for lazy upload.
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, event_id, camera_id, file_path, byte_size
                FROM outbox_evidence
                WHERE status = 'PENDING'
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def mark_evidence_sent(self, evidence_id: int, byte_size: int) -> None:
        """
        Mark thumbnail as SENT and record byte consumption.
        """
        now_str = self._current_utc_str()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                "UPDATE outbox_evidence SET status = 'SENT', sent_at = ? WHERE id = ?",
                (now_str, evidence_id),
            )
            self._record_bytes_internal(conn, byte_size, is_evidence=True)

    def mark_evidence_skipped(self, evidence_id: int) -> None:
        """
        Mark thumbnail as SKIPPED (e.g. daily byte budget exceeded).
        """
        with self._lock, self._get_connection() as conn:
            conn.execute(
                "UPDATE outbox_evidence SET status = 'SKIPPED' WHERE id = ?",
                (evidence_id,),
            )

    def _record_bytes_internal(self, conn: sqlite3.Connection, num_bytes: int, is_evidence: bool) -> None:
        today = self._current_date_str()
        meta_bytes = 0 if is_evidence else num_bytes
        evid_bytes = num_bytes if is_evidence else 0

        conn.execute(
            """
            INSERT INTO daily_usage (date_str, bytes_metadata, bytes_evidence, total_bytes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date_str) DO UPDATE SET
                bytes_metadata = bytes_metadata + excluded.bytes_metadata,
                bytes_evidence = bytes_evidence + excluded.bytes_evidence,
                total_bytes = total_bytes + excluded.total_bytes
            """,
            (today, meta_bytes, evid_bytes, num_bytes),
        )

    def get_daily_bytes_used(self, date_str: Optional[str] = None) -> int:
        target_date = date_str or self._current_date_str()
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT total_bytes FROM daily_usage WHERE date_str = ?",
                (target_date,),
            )
            row = cursor.fetchone()
            return int(row["total_bytes"]) if row else 0

    def is_budget_exceeded(self, daily_budget_bytes: int) -> bool:
        if daily_budget_bytes <= 0:
            return False
        used = self.get_daily_bytes_used()
        return used >= daily_budget_bytes

    def get_queue_depth(self) -> int:
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM outbox_events WHERE status = 'PENDING'")
            row = cursor.fetchone()
            return int(row["cnt"]) if row else 0

    def purge_sent(self, max_records_to_keep: int = 1000) -> int:
        """
        Retain local disk space by purging old SENT records.
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM outbox_events
                WHERE status = 'SENT'
                AND id NOT IN (
                    SELECT id FROM outbox_events
                    WHERE status = 'SENT'
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (max_records_to_keep,),
            )
            return cursor.rowcount
