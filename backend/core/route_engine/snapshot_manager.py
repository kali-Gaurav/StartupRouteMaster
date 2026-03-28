import pickle
import os
import asyncio
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
    def __init__(self, snapshot_dir: Optional[str] = None):
        from database.config import Config
        self.snapshot_dir = snapshot_dir or Config.SNAPSHOT_DIR
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
        Includes version validation to force rebuilds on schema changes.
        """
        date_str = date.strftime("%Y%m%d")
        
        # Layer 1: Redis
        try:
            await multi_layer_cache.initialize()
            snapshot = await multi_layer_cache.get_graph_snapshot(date_str)
            if snapshot:
                # [Task 27.18] Version Validation
                if getattr(snapshot, 'version', None) != StaticGraphSnapshot.version:
                    logger.warning(f"🔄 Redis snapshot version mismatch ({getattr(snapshot, 'version', 'None')} != {StaticGraphSnapshot.version}). Forcing rebuild.")
                else:
                    logger.info(f"🚀 Loaded snapshot for {date_str} from Redis (v{snapshot.version}).")
                    return snapshot
        except Exception as e:
            logger.warning(f"Redis snapshot load failed: {e}")

        # Layer 2: Disk
        filename = self._get_filename(date)
        if os.path.exists(filename):
            try:
                def load_from_disk():
                    with open(filename, 'rb') as f:
                        return pickle.load(f)
                
                snapshot = await asyncio.to_thread(load_from_disk)
                
                # [Task 27.18] Version Validation
                if getattr(snapshot, 'version', None) != StaticGraphSnapshot.version:
                    logger.warning(f"🔄 Disk snapshot version mismatch. Forcing rebuild.")
                    try: os.remove(filename) 
                    except: pass
                else:
                    logger.info(f"💾 Loaded snapshot for {date_str} from disk (v{snapshot.version}).")
                    
                    # [Task 121: Elite JIT Patching] Ensure Nexus MemMaps are re-linked
                    is_legacy = not hasattr(snapshot, '_trip_to_pid') or snapshot._trip_to_pid is None
                    is_empty = not hasattr(snapshot, '_trip_reachability_bitset') or snapshot._trip_reachability_bitset is None
                    
                    if is_legacy or is_empty:
                        logger.info(f"⚡ [NEXUS:JIT] Hydrating snapshot {date_str} MemMaps/Indices...")
                        try: snapshot.vectorize()
                        except Exception as e: logger.error(f"Nexus JIT Hydration Failed: {e}")
                    
                    # Proactive Hydration: Save to Redis for next time
                    try: await multi_layer_cache.set_graph_snapshot(date_str, snapshot)
                    except: pass
                    return snapshot
            except Exception as e:
                logger.error(f"Failed to load snapshot from disk: {e}")
        
        return None

    def load_snapshot_sync(self, date: datetime) -> Optional[StaticGraphSnapshot]:
        """
        Synchronous wrapper for load_snapshot. 
        Only uses Layer 2 (Disk) to avoid nested event loop issues in threaded logic.
        """
        filename = self._get_filename(date)
        if os.path.exists(filename):
            try:
                with open(filename, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"SnapshotManager: Sync Disk Load Failed: {e}")
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

    async def purge_old_snapshots(self, keep_days: int = 2):
        """
        Subtask 5.6: Automated Snapshot Eviction.
        Deletes disk and Redis snapshots older than keep_days.
        Also cleans up associated MEMMAP files.
        """
        from datetime import timedelta
        threshold = datetime.now() - timedelta(days=keep_days)
        threshold_str = threshold.strftime("%Y%m%d")
        
        logger.info(f"🧹 Snapshot Manager: Purging snapshots older than {threshold_str}")
        
        # 1. Clean Disk Pickles
        files = await self.list_snapshots()
        for f in files:
            # Extract date from filename: graph_snapshot_YYYYMMDD.pkl
            try:
                ds = f.split("_")[-1].split(".")[0]
                if ds < threshold_str:
                    path = os.path.join(self.snapshot_dir, f)
                    os.remove(path)
                    logger.info(f"  🗑️ Deleted old snapshot: {f}")
                    
                    # Also clean Redis
                    if multi_layer_cache.redis:
                        await multi_layer_cache.redis.delete(f"graph:snapshot:{ds}")
            except: continue

        # 2. Clean MemMap Directory (Subtask 5.1 cleanup)
        from database.config import Config
        if os.path.exists(Config.MEMMAP_DIR):
            for f in os.listdir(Config.MEMMAP_DIR):
                f_path = os.path.join(Config.MEMMAP_DIR, f)
                # If file was modified more than keep_days ago
                if os.path.getmtime(f_path) < threshold.timestamp():
                    try:
                        os.remove(f_path)
                        logger.info(f"  🗑️ Deleted old memmap file: {f}")
                    except: pass
