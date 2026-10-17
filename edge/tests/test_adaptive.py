"""
Unit tests for the Adaptive Resource Controller.
Tests automatic profile downgrading under load, recovery when healthy, and thumbnail policies.
"""

import pytest
from edge.adaptive import AdaptiveController
from edge.config import EdgeConfig
from edge.outbox import OutboxQueue


@pytest.fixture
def adaptive_setup(tmp_path):
    db_file = tmp_path / "test_adaptive.db"
    outbox = OutboxQueue(db_path=str(db_file))
    config = EdgeConfig(
        profile_name="normal",
        cpu_high_threshold=80.0,
        cpu_low_threshold=40.0,
        queue_high_threshold=50,
        queue_low_threshold=10,
        daily_budget_bytes=5000,
    )
    controller = AdaptiveController(config=config, outbox=outbox)
    return controller, outbox, config


def test_adaptive_downgrade_on_high_load(adaptive_setup):
    controller, outbox, _ = adaptive_setup
    assert controller.current_profile_name == "normal"

    # Simulate high CPU
    controller.get_system_metrics = lambda: {"cpu_percent": 88.0, "memory_percent": 70.0, "queue_depth": 5}

    # Tick 1: Stress detected
    p, msg = controller.evaluate_adaptive_state()
    assert controller.current_profile_name == "normal"

    # Tick 2: Consecutive stress triggers downgrade to 'low'
    p, msg = controller.evaluate_adaptive_state()
    assert controller.current_profile_name == "low"
    assert "low" in msg

    # Tick 3 & 4: Sustained stress triggers downgrade to 'ultra_low'
    controller.evaluate_adaptive_state()
    p, msg = controller.evaluate_adaptive_state()
    assert controller.current_profile_name == "ultra_low"
    assert p.input_resolution == 320
    assert p.sample_interval_sec == 60.0


def test_adaptive_recovery_on_calm(adaptive_setup):
    controller, outbox, _ = adaptive_setup
    controller.current_profile_name = "ultra_low"

    # Simulate calm CPU and empty queue
    controller.get_system_metrics = lambda: {"cpu_percent": 25.0, "memory_percent": 30.0, "queue_depth": 0}

    # Needs 3 consecutive calm ticks to recover to 'low'
    controller.evaluate_adaptive_state()
    controller.evaluate_adaptive_state()
    p, msg = controller.evaluate_adaptive_state()
    assert controller.current_profile_name == "low"

    # Next 3 calm ticks recover to 'normal'
    controller.evaluate_adaptive_state()
    controller.evaluate_adaptive_state()
    p, msg = controller.evaluate_adaptive_state()
    assert controller.current_profile_name == "normal"
    assert p.input_resolution == 640
    assert p.sample_interval_sec == 15.0


def test_evidence_policy_and_budget_fallback(adaptive_setup):
    controller, outbox, config = adaptive_setup

    # Normal profile allows evidence
    assert controller.should_generate_evidence(is_deficit=False) is True

    # Low profile only allows evidence if deficit detected
    controller.current_profile_name = "low"
    assert controller.should_generate_evidence(is_deficit=False) is False
    assert controller.should_generate_evidence(is_deficit=True) is True

    # Ultra-low profile never allows thumbnails
    controller.current_profile_name = "ultra_low"
    assert controller.should_generate_evidence(is_deficit=True) is False

    # Budget exceeded fallback
    controller.current_profile_name = "normal"
    outbox.enqueue_event({"event_id": "e_budget"})
    outbox.mark_events_sent(["e_budget"], transferred_bytes=6000)  # > 5000 budget
    assert controller.should_generate_evidence(is_deficit=True) is False
