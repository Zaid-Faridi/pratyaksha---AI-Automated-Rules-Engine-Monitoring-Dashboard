"""
Local Batch Schedule and Sanctioned Inventory Cache for Pratyaksha Edge.
Enables offline pre-checks and compute preservation by skipping inference outside active batch hours.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

from edge.config import EdgeConfig


class ScheduleCache:
    """
    Caches batch schedules and sanctioned inventory locally on edge.
    Automatically refreshes when online and provides active batch checks.
    """
    def __init__(self, config: EdgeConfig) -> None:
        self.config = config
        self.cache_path = Path(config.cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_refresh_time = 0.0

        # In-memory storage
        self.batches: List[Dict[str, Any]] = []
        self.inventory: List[Dict[str, Any]] = []

        # Load from disk cache initially
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.batches = data.get("batches", [])
                    self.inventory = data.get("inventory", [])
            except Exception:
                self.batches = []
                self.inventory = []

    def _save_to_disk(self) -> None:
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "centre_id": self.config.centre_id,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "batches": self.batches,
                        "inventory": self.inventory,
                    },
                    f,
                    indent=2,
                )
        except Exception:
            pass

    def refresh_from_backend(self) -> bool:
        """
        Query backend for latest batch schedules and inventory.
        Gracefully falls back to disk cache on connection errors.
        """
        headers = {}
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key

        try:
            # 1. Fetch batches
            batch_url = f"{self.config.backend_url}/batches?centre_id={self.config.centre_id}"
            resp_b = requests.get(batch_url, headers=headers, timeout=self.config.request_timeout_sec)
            if resp_b.status_code == 200:
                self.batches = resp_b.json()

            # 2. Fetch sanctioned inventory
            inv_url = f"{self.config.backend_url}/inventory?centre_id={self.config.centre_id}"
            resp_i = requests.get(inv_url, headers=headers, timeout=self.config.request_timeout_sec)
            if resp_i.status_code == 200:
                self.inventory = resp_i.json()

            self._save_to_disk()
            self.last_refresh_time = time.time()
            return True
        except Exception:
            # Offline or unreachable; use existing cached values
            return False

    def is_batch_active(self, now_dt: Optional[datetime] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check whether an authorized training batch is currently running.
        Returns (is_active, active_batch_dict).
        """
        dt = now_dt or datetime.now()
        day_name = dt.strftime("%A")  # e.g. "Monday"
        current_time_str = dt.strftime("%H:%M")  # e.g. "10:30"

        # If no batches exist in cache, default to permissive (active) so sampling proceeds
        if not self.batches:
            return True, None

        for batch in self.batches:
            days = batch.get("days", [])
            # Check weekday
            if day_name in days or not days:
                start = batch.get("start_time", "00:00")
                end = batch.get("end_time", "23:59")
                if start <= current_time_str <= end:
                    return True, batch

        return False, None

    def get_expected_inventory(self, zone: str) -> Dict[str, int]:
        """
        Return mapping of {item_name: expected_count} for a given zone.
        """
        result = {}
        for entry in self.inventory:
            if entry.get("zone") == zone:
                result[entry.get("item", "")] = int(entry.get("expected_count", 0))
        return result
