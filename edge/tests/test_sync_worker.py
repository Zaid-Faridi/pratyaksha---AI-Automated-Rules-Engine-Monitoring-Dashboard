"""
Unit tests for the Background Sync Worker.
Tests network retry backoff, gzip payload compression, and offline queue preservation.
"""

from unittest.mock import MagicMock, patch
import pytest
from edge.adaptive import AdaptiveController
from edge.config import EdgeConfig
from edge.outbox import OutboxQueue
from edge.sync_worker import SyncWorker


@pytest.fixture
def sync_setup(tmp_path):
    db_file = tmp_path / "test_sync.db"
    outbox = OutboxQueue(db_path=str(db_file))
    config = EdgeConfig(
        backend_url="http://mock-backend:8088",
        db_path=str(db_file),
        daily_budget_bytes=10000,
    )
    adaptive = AdaptiveController(config=config, outbox=outbox)
    worker = SyncWorker(config=config, outbox=outbox, adaptive=adaptive)
    return worker, outbox, config


def test_sync_success_clears_outbox(sync_setup):
    worker, outbox, _ = sync_setup

    # Enqueue 2 events
    outbox.enqueue_event({"event_id": "ev-01", "camera_id": "cam_01", "val": 1})
    outbox.enqueue_event({"event_id": "ev-02", "camera_id": "cam_01", "val": 2})
    assert outbox.get_queue_depth() == 2

    # Mock 201 Created from backend
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"status": "success", "events_ingested": 2}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        synced = worker.sync_events_batch()
        assert synced == 2
        assert outbox.get_queue_depth() == 0
        assert mock_post.called

        # Verify Content-Encoding: gzip header was sent
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["Content-Encoding"] == "gzip"


def test_sync_failure_retains_events_and_applies_backoff(sync_setup):
    worker, outbox, _ = sync_setup

    outbox.enqueue_event({"event_id": "ev-fail-01", "camera_id": "cam_01"})
    assert outbox.get_queue_depth() == 1

    # Mock connection error
    with patch("requests.post", side_effect=Exception("Connection refused")):
        with patch("time.sleep"):  # Speed up test
            synced = worker.sync_events_batch()
            assert synced == 0
            # Event is NOT lost!
            assert outbox.get_queue_depth() == 1
            # Backoff increased
            assert worker.current_backoff_sec > 1.0


def test_heartbeat_telemetry_reporting(sync_setup):
    worker, outbox, _ = sync_setup

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "success",
        "agent_health": "healthy",
        "queue_depth": 0,
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        success = worker.send_heartbeat(force=True)
        assert success is True
        assert mock_post.called
        data = mock_post.call_args[1]["json"]
        assert "queue_depth" in data
        assert "cpu_percent" in data
        assert "memory_percent" in data
