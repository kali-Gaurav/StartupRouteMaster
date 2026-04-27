"""
Unit tests for the orchestrator reconciliation worker.
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

backend_path = os.path.abspath(os.path.dirname(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from workers import orchestrator


def test_start_and_stop_reconciliation_worker(monkeypatch):
    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()
    mock_scheduler.start = MagicMock()
    mock_scheduler.shutdown = MagicMock()

    monkeypatch.setattr(orchestrator, "BackgroundScheduler", lambda: mock_scheduler)
    monkeypatch.setattr(
        orchestrator,
        "Config",
        SimpleNamespace(
            PAYMENT_RECONCILIATION_INTERVAL_MINUTES=1,
            INVENTORY_RECONCILIATION_INTERVAL_SECONDS=1,
        ),
    )

    orchestrator.scheduler = None
    orchestrator.start_reconciliation_worker()

    assert orchestrator.scheduler is mock_scheduler
    assert mock_scheduler.add_job.call_count == 4
    mock_scheduler.start.assert_called_once()

    orchestrator.stop_reconciliation_worker()
    assert orchestrator.scheduler is None
    mock_scheduler.shutdown.assert_called_once()


def test_start_reconciliation_worker_is_idempotent(monkeypatch):
    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()
    mock_scheduler.start = MagicMock()

    monkeypatch.setattr(orchestrator, "BackgroundScheduler", lambda: mock_scheduler)
    monkeypatch.setattr(
        orchestrator,
        "Config",
        SimpleNamespace(
            PAYMENT_RECONCILIATION_INTERVAL_MINUTES=1,
            INVENTORY_RECONCILIATION_INTERVAL_SECONDS=1,
        ),
    )

    orchestrator.scheduler = mock_scheduler
    orchestrator.start_reconciliation_worker()
    assert orchestrator.scheduler is mock_scheduler
    assert mock_scheduler.add_job.call_count == 0
    mock_scheduler.start.assert_not_called()
