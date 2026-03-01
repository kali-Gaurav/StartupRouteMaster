import pickle
import os
from datetime import datetime
from typing import Optional, Any
import logging

from .graph import StaticGraphSnapshot
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger(__name__)

EXPECTED_SNAPSHOT_VERSION = "v2.5" # Bump this whenever graph structure or builder logic changes

class SnapshotManager:
    """Enhanced SnapshotManager with Redis support."""

    def __init__(self, snapshot_dir: str = "snapshots"):
        self.snapshot_dir = snapshot_dir
        if not os.path.exists(self.snapshot_dir):
            os.makedirs(self.snapshot_dir, exist_ok=True)

    def _get_snapshot_path(self, date: datetime) -> str:
        filename = f"graph_snapshot_{date.strftime('%Y%m%d')}.pkl"
        return os.path.join(self.snapshot_dir, filename)

    async def save_snapshot(self, snapshot: StaticGraphSnapshot) -> Optional[str]:
        if not snapshot:
            logger.warning("Attempted to save empty snapshot")
            return None
        
        # Ensure version is set before saving
        snapshot.version = EXPECTED_SNAPSHOT_VERSION
        date_str = snapshot.date.strftime('%Y%m%d')
        
        # 1. Save to Redis (Phase 10: Distributed Control Plane)
        try:
            await multi_layer_cache.initialize()
            await multi_layer_cache.set_graph_snapshot(date_str, snapshot)
            logger.info(f"Snapshot for {date_str} pushed to Redis.")
        except Exception as re:
            logger.warning(f"Failed to save snapshot to Redis: {re}")

        # 2. Save to Disk (Local fallback)
        try:
            path = self._get_snapshot_path(snapshot.date)
            with open(path, "wb") as f:
                pickle.dump(snapshot, f)
            logger.info(f"Snapshot saved to disk: {path}")
            return path
        except Exception as e:
            logger.error(f"Error saving snapshot to disk: {e}")
            return None

    async def load_snapshot(self, date: datetime) -> Optional[StaticGraphSnapshot]:
        """Load a previously saved snapshot for the given date (Redis first, then disk)."""
        date_str = date.strftime('%Y%m%d')
        
        # 1. Try Redis
        try:
            await multi_layer_cache.initialize()
            snapshot = await multi_layer_cache.get_graph_snapshot(date_str)
            if snapshot:
                if getattr(snapshot, 'version', None) == EXPECTED_SNAPSHOT_VERSION:
                    logger.info(f"Loaded snapshot for {date_str} from Redis.")
                    return snapshot
                else:
                    logger.warning(f"Redis snapshot version mismatch: {getattr(snapshot, 'version', 'none')} != {EXPECTED_SNAPSHOT_VERSION}")
        except Exception as re:
            logger.warning(f"Redis snapshot load failed: {re}")

        # 2. Try Disk
        path = self._get_snapshot_path(date)
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    snapshot = pickle.load(f)
                
                if getattr(snapshot, 'version', None) == EXPECTED_SNAPSHOT_VERSION:
                    logger.info(f"Loaded snapshot for {date_str} from disk.")
                    return snapshot
                else:
                    logger.warning(f"Disk snapshot version mismatch: {getattr(snapshot, 'version', 'none')} != {EXPECTED_SNAPSHOT_VERSION}")
                    # Force delete stale disk snapshot to trigger fresh build on next attempt
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            except (pickle.UnpicklingError, EOFError, AttributeError, Exception) as e:
                logger.error(f"Snapshot corruption detected for {date_str}: {e}. Triggering automatic rebuild.")
                # Force delete corrupted file
                try:
                    os.remove(path)
                except Exception:
                    pass
        
        return None
        
    async def save_hub_table(self, table: Any, date: datetime) -> Optional[str]:
        if not table: return None
        path = os.path.join(self.snapshot_dir, f"hub_table_{date.strftime('%Y%m%d')}.pkl")
        try:
            with open(path, "wb") as f:
                pickle.dump(table, f)
            logger.info(f"Hub table saved to {path}")
            return path
        except Exception as e:
            logger.error(f"Error saving hub table: {e}")
            return None

    async def load_hub_table(self, date: datetime) -> Optional[Any]:
        path = os.path.join(self.snapshot_dir, f"hub_table_{date.strftime('%Y%m%d')}.pkl")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"Error loading hub table: {e}")
        return None
