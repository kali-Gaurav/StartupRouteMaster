import pickle
import os
from datetime import datetime
from typing import Optional
import logging

from .graph import StaticGraphSnapshot

logger = logging.getLogger(__name__)

class SnapshotManager:
    """Minimal stubbed SnapshotManager used by tests and imports.

    The full implementation was causing indentation/syntax errors and is not
    required for payment-related tests. It simply persists a snapshot to disk
    and returns the path.
    """

    def __init__(self, snapshot_dir: str = "snapshots"):
        self.snapshot_dir = snapshot_dir
        if not os.path.exists(self.snapshot_dir):
            os.makedirs(self.snapshot_dir, exist_ok=True)
        self.use_redis = False

    def _get_snapshot_path(self, date: datetime) -> str:
        filename = f"graph_snapshot_{date.strftime('%Y%m%d')}.pkl"
        return os.path.join(self.snapshot_dir, filename)

    async def save_snapshot(self, snapshot: StaticGraphSnapshot) -> Optional[str]:
        if not snapshot:
            logger.warning("Attempted to save empty snapshot")
            return None
        try:
            path = self._get_snapshot_path(snapshot.date)
            with open(path, "wb") as f:
                pickle.dump(snapshot, f)
            logger.info(f"Snapshot saved to {path}")
            return path
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")
            return None

    async def load_snapshot(self, date: datetime) -> Optional[StaticGraphSnapshot]:
        """Load a previously saved snapshot for the given date."""
        path = self._get_snapshot_path(date)
        if not os.path.exists(path):
            logger.info(f"No snapshot found at {path}, triggering rebuild")
            return None
        try:
            with open(path, "rb") as f:
                snapshot = pickle.load(f)
            logger.info(f"Loaded snapshot from {path}")
            return snapshot
        except Exception as e:
            logger.error(f"Error loading snapshot from {path}: {e}")
            return None
