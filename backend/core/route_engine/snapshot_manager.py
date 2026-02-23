import pickle
import os
import asyncio
from datetime import datetime
from typing import Optional
import logging

from .graph import StaticGraphSnapshot
from ...services.multi_layer_cache import multi_layer_cache
from ...database.config import Config

logger = logging.getLogger(__name__)

class SnapshotManager:
    """
    Manages entries for StaticGraphSnapshot objects using local files and Redis (Phase 10).
    Redis acts as the primary distributed high-speed store.
    """

    def __init__(self, snapshot_dir: str = "snapshots"):
        self.snapshot_dir = snapshot_dir
        if not os.path.exists(self.snapshot_dir):
            os.makedirs(self.snapshot_dir, exist_ok=True)
        # Force Redis disabled for local development/testing unless explicitly requested
        self.use_redis = False

    def _get_snapshot_path(self, date: datetime) -> str:
        """Generates a file path for a given date's snapshot."""
        filename = f"graph_snapshot_{date.strftime('%Y%m%d')}.pkl"
        return os.path.join(self.snapshot_dir, filename)

    async def save_snapshot(self, snapshot: StaticGraphSnapshot) -> Optional[str]:
        """
        Saves a StaticGraphSnapshot object to Redis and local file.
        """
        if not snapshot:
            logger.warning("Attempted to save an empty snapshot.")
            return None
        
        # 1. Save to Redis (Phase 10) - DISABLED
        if self.use_redis:
            pass

        # 2. Persist to local file for recovery
        filepath = self._get_snapshot_path(snapshot.date)
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(snapshot, f)
            logger.info(f"Snapshot saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save snapshot to file: {e}")
            return None

    async def load_snapshot(self, date: datetime) -> Optional[StaticGraphSnapshot]:
        """
        Loads a StaticGraphSnapshot object from local file (Redis disabled).
        """
        # 1. Try Redis First (Phase 10) - DISABLED
        if self.use_redis:
            pass

        # 2. Fallback to local file
        filepath = self._get_snapshot_path(date)
        abs_path = os.path.abspath(filepath)
        print(f"DEBUG_SM: Checking for snapshot at {abs_path}")
        if os.path.exists(filepath):
            try:
                with open(filepath, 'rb') as f:
                    snapshot = pickle.load(f)
                print(f"DEBUG_SM: Loaded snapshot from {abs_path}")
                return snapshot
            except Exception as e:
                logger.error(f"Failed to load snapshot from file {filepath}: {e}")
        else:
            print(f"DEBUG_SM: Snapshot NOT found at {abs_path}")
        
        return None
