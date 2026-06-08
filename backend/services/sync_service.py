"""
Re-export shim for services.sync_service.

The canonical implementation lives in services.data.sync.
This module exists to maintain backward compatibility with:
  - workers/background_worker.py
  - services/orchestration/registry.py
"""

from services.data.sync import (  # noqa: F401
    HeartbeatSyncAgent,
    HeartbeatSyncAgentMetrics,
    HeartbeatScheduler,
    AegisChaosDrill,
)
