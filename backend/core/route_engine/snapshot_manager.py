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
        os.makedirs(self.snapshot_dir, exist_ok=True)
        self.use_redis = getattr(Config, "REDIS_SNAPSHOT_ENABLED", True)

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
        
        date_str = snapshot.date.strftime('%Y%m%d')
        
        # 1. Save to Redis (Phase 10)
        if self.use_redis:
            try:
                await multi_layer_cache.initialize()
                await multi_layer_cache.set_graph_snapshot(date_str, snapshot)
                logger.info(f"Snapshot for {date_str} stored in Redis.")
            except Exception as e:
                logger.warning(f"Failed to save snapshot to Redis: {e}")

        # 2. Persist to local file for recovery
        filepath = self._get_snapshot_path(snapshot.date)
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(snapshot, f)
            logger.info(f"Persistant copy of snapshot {date_str} saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save file snapshot to {filepath}: {e}")
            return None

    async def load_snapshot(self, date: datetime) -> Optional[StaticGraphSnapshot]:
        """
        Loads a StaticGraphSnapshot object from Redis, falling back to local file.
        """
        date_str = date.strftime('%Y%m%d')

        # 1. Try Redis First (Phase 10)
        if self.use_redis:
            try:
                await multi_layer_cache.initialize()
                snapshot = await multi_layer_cache.get_graph_snapshot(date_str)
                if snapshot:
                    logger.info(f"Snapshot for {date_str} loaded from Redis (Cache Hit)")
                    return snapshot
            except Exception as e:
                logger.debug(f"Redis snapshot load failed (will fallback): {e}")

        # 2. Fallback to local file
        filepath = self._get_snapshot_path(date)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'rb') as f:
                    snapshot = pickle.load(f)
                logger.info(f"Snapshot for {date_str} loaded from file fallback")
                
                # Side-effect: Re-populate Redis if it was a miss
                if self.use_redis:
                    asyncio.create_task(multi_layer_cache.set_graph_snapshot(date_str, snapshot))
                
                return snapshot
            except Exception as e:
                logger.error(f"Failed to load snapshot from file {filepath}: {e}")
        
        logger.info(f"No snapshot found for {date_str} in any store.")
        return None
