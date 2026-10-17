"""
Unit tests for the SQLite Outbox Queue.
Tests crash safety, idempotency, byte budget tracking, and retention purging.
"""

from pathlib import Path
import pytest
from edge.outbox import OutboxQueue


@pytest.fixture
def temp_outbox(tmp_path):
    db_file = tmp_path / "test_outbox.db"
    return OutboxQueue(db_path=str(db_file))


def test_enqueue_and_idempotency(temp_outbox):
    event_data = {
        "event_id": "test-uuid-1234",
        "camera_id": "cam_01",
        "zone": "classroom",
        "person_count": {"raw": 10, "smoothed": 10},
    }

    # 1. First enqueue
    eid1 = temp_outbox.enqueue_event(event_data)
    assert eid1 == "test-uuid-1234"
    assert temp_outbox.get_queue_depth() == 1

    # 2. Duplicate enqueue with same event_id -> should be ignored (idempotent)
    eid2 = temp_outbox.enqueue_event(event_data)
    assert eid2 == "test-uuid-1234"
    assert temp_outbox.get_queue_depth() == 1


def test_outbox_batch_and_sent_flow(temp_outbox):
    # Enqueue 3 events
    for i in range(3):
        temp_outbox.enqueue_event({
            "camera_id": "cam_01",
            "zone": "classroom",
            "val": i,
        })

    assert temp_outbox.get_queue_depth() == 3

    # Fetch batch of 2
    batch = temp_outbox.get_pending_events(limit=2)
    assert len(batch) == 2
    event_ids = [e["event_id"] for e in batch]

    # Mark as sent with 450 bytes transferred
    temp_outbox.mark_events_sent(event_ids, transferred_bytes=450)
    assert temp_outbox.get_queue_depth() == 1

    # Daily usage should reflect transferred bytes
    used = temp_outbox.get_daily_bytes_used()
    assert used == 450


def test_daily_budget_accounting(temp_outbox):
    assert temp_outbox.is_budget_exceeded(daily_budget_bytes=1000) is False

    # Simulate sending 1200 bytes
    temp_outbox.enqueue_event({"camera_id": "cam_01", "event_id": "e1"})
    temp_outbox.mark_events_sent(["e1"], transferred_bytes=1200)

    assert temp_outbox.get_daily_bytes_used() == 1200
    assert temp_outbox.is_budget_exceeded(daily_budget_bytes=1000) is True


def test_purge_sent(temp_outbox):
    for i in range(10):
        eid = temp_outbox.enqueue_event({"event_id": f"event_{i}"})
        temp_outbox.mark_events_sent([f"event_{i}"])

    assert temp_outbox.get_queue_depth() == 0

    # Purge keeping only the 3 most recent
    purged = temp_outbox.purge_sent(max_records_to_keep=3)
    assert purged == 7
