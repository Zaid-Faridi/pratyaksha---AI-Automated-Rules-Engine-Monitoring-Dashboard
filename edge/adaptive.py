"""
Adaptive Behavior and Resource Controller for Pratyaksha Edge.
Dynamically adjusts sampling frequency, input resolution, and thumbnail generation
based on local CPU load, memory utilization, and outbox queue depth.
"""

from typing import Dict, Optional, Tuple
import psutil

from edge.config import PROFILES, EdgeConfig, EdgeProfile
from edge.outbox import OutboxQueue


class AdaptiveController:
    """
    Monitors hardware resources and automatically switches profiles
    between 'normal', 'low', and 'ultra_low'.
    """
    def __init__(self, config: EdgeConfig, outbox: OutboxQueue) -> None:
        self.config = config
        self.outbox = outbox
        self.current_profile_name = config.profile_name
        self._stress_ticks = 0
        self._calm_ticks = 0

    @property
    def current_profile(self) -> EdgeProfile:
        return PROFILES.get(self.current_profile_name, PROFILES["normal"])

    def get_system_metrics(self) -> Dict[str, float]:
        """
        Sample current CPU, memory, and queue depth.
        """
        try:
            cpu = float(psutil.cpu_percent(interval=None))
            mem = float(psutil.virtual_memory().percent)
        except Exception:
            cpu = 25.0
            mem = 35.0

        queue_depth = self.outbox.get_queue_depth()
        return {
            "cpu_percent": cpu,
            "memory_percent": mem,
            "queue_depth": queue_depth,
        }

    def evaluate_adaptive_state(self) -> Tuple[EdgeProfile, str]:
        """
        Check metrics and adjust profile up or down with anti-flapping hysteresis.
        Returns (current_profile, status_message).
        """
        metrics = self.get_system_metrics()
        cpu = metrics["cpu_percent"]
        q_depth = metrics["queue_depth"]

        is_stressed = (
            cpu >= self.config.cpu_high_threshold or
            q_depth >= self.config.queue_high_threshold
        )
        is_calm = (
            cpu <= self.config.cpu_low_threshold and
            q_depth <= self.config.queue_low_threshold
        )

        msg = "Stable"

        if is_stressed:
            self._stress_ticks += 1
            self._calm_ticks = 0
            # Downgrade after 2 consecutive stress samples
            if self._stress_ticks >= 2:
                if self.current_profile_name == "normal":
                    self.current_profile_name = "low"
                    msg = f"Auto-downgraded to 'low' profile (CPU: {cpu:.1f}%, Queue: {q_depth})"
                    self._stress_ticks = 0
                elif self.current_profile_name == "low":
                    self.current_profile_name = "ultra_low"
                    msg = f"Auto-downgraded to 'ultra_low' profile (CPU: {cpu:.1f}%, Queue: {q_depth})"
                    self._stress_ticks = 0
        elif is_calm:
            self._calm_ticks += 1
            self._stress_ticks = 0
            # Recover after 3 consecutive calm samples
            if self._calm_ticks >= 3:
                if self.current_profile_name == "ultra_low":
                    self.current_profile_name = "low"
                    msg = f"Auto-recovered to 'low' profile (CPU: {cpu:.1f}%, Queue: {q_depth})"
                    self._calm_ticks = 0
                elif self.current_profile_name == "low":
                    self.current_profile_name = "normal"
                    msg = f"Auto-recovered to 'normal' profile (CPU: {cpu:.1f}%, Queue: {q_depth})"
                    self._calm_ticks = 0
        else:
            self._stress_ticks = max(0, self._stress_ticks - 1)
            self._calm_ticks = max(0, self._calm_ticks - 1)

        return self.current_profile, msg

    def should_generate_evidence(self, is_deficit: bool) -> bool:
        """
        Decide whether to create an evidence thumbnail based on budget and profile.
        """
        # 1. Daily byte budget check
        if self.outbox.is_budget_exceeded(self.config.daily_budget_bytes):
            return False

        profile = self.current_profile
        # 2. Profile policy
        if not profile.evidence_thumbnails_enabled:
            return False

        if profile.evidence_on_deficit_only and not is_deficit:
            return False

        return True
