import pickle
import os
from datetime import datetime
from typing import Optional, Any, List, Tuple
import logging

from .graph import StaticGraphSnapshot
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger(__name__)

class SnapshotManager:
    """
    Task 19: High-Performance Snapshot Management.
    Handles persistence of graph state across RAM, Redis, and Disk.
    """
    def __init__(self, snapshot_dir: str = "snapshots"):
        self.snapshot_dir = snapshot_dir
        if not os.path.exists(self.snapshot_dir):
            os.makedirs(self.snapshot_dir)

    def _get_filename(self, date: datetime) -> str:
        date_str = date.strftime("%Y%m%d")
        return os.path.join(self.snapshot_dir, f"graph_snapshot_{date_str}.pkl")

    async def load_snapshot(self, date: datetime) -> Optional[StaticGraphSnapshot]:
        """
        Loads snapshot using prioritized layers:
        1. Redis (RAM speed)
        2. Disk (Persistent fallback)
        """
        date_str = date.strftime("%Y%m%d")
        
        # Layer 1: Redis
        try:
            await multi_layer_cache.initialize()
            snapshot = await multi_layer_cache.get_graph_snapshot(date_str)
            if snapshot:
                logger.info(f"🚀 Loaded snapshot for {date_str} from Redis.")
                return snapshot
        except Exception as e:
            logger.warning(f"Redis snapshot load failed: {e}")

        # Layer 2: Disk
        filename = self._get_filename(date)
        if os.path.exists(filename):
            try:
                with open(filename, 'rb') as f:
                    snapshot = pickle.load(f)
                logger.info(f"💾 Loaded snapshot for {date_str} from disk.")
                # Proactive Hydration: Save to Redis for next time
                await self.save_snapshot(snapshot)
                return snapshot
            except Exception as e:
                logger.error(f"Failed to load snapshot from disk: {e}")
        
        return None

    async def save_snapshot(self, snapshot: StaticGraphSnapshot):
        """Saves snapshot to both Disk and Redis."""
        date_str = snapshot.date.strftime("%Y%m%d")
        
        # 1. Save to Disk (Reliability)
        filename = self._get_filename(snapshot.date)
        try:
            with open(filename, 'wb') as f:
                pickle.dump(snapshot, f)
            logger.info(f"Snapshot saved to disk: {filename}")
        except Exception as e:
            logger.error(f"Failed to save snapshot to disk: {e}")

        # 2. Save to Redis (Performance)
        try:
            await multi_layer_cache.initialize()
            await multi_layer_cache.set_graph_snapshot(date_str, snapshot)
        except Exception as e:
            logger.warning(f"Failed to save snapshot to Redis: {e}")

    async def list_snapshots(self) -> List[str]:
        return [f for f in os.listdir(self.snapshot_dir) if f.endswith(".pkl")]

    async def delete_snapshot(self, date: datetime):
        filename = self._get_filename(date)
        if os.path.exists(filename):
            os.remove(filename)
        
        date_str = date.strftime("%Y%m%d")
        if multi_layer_cache.redis:
            await multi_layer_cache.redis.delete(f"graph:snapshot:{date_str}")
