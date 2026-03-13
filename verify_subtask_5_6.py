import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.core.route_engine.snapshot_manager import SnapshotManager
from backend.database.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-5.6")

async def test_snapshot_purging():
    sm = SnapshotManager(snapshot_dir="test_snapshots")
    if not os.path.exists("test_snapshots"):
        os.makedirs("test_snapshots")
        
    try:
        # 1. Create dummy files
        # A. Old file (3 days ago)
        old_date = datetime.now() - timedelta(days=3)
        old_file = os.path.join("test_snapshots", f"graph_snapshot_{old_date.strftime('%Y%m%d')}.pkl")
        with open(old_file, 'w') as f: f.write("dummy old data")
        
        # B. New file (today)
        new_date = datetime.now()
        new_file = os.path.join("test_snapshots", f"graph_snapshot_{new_date.strftime('%Y%m%d')}.pkl")
        with open(new_file, 'w') as f: f.write("dummy new data")
        
        # C. Old MemMap file (In the real Config.MEMMAP_DIR)
        os.makedirs(Config.MEMMAP_DIR, exist_ok=True)
        old_mmap = os.path.join(Config.MEMMAP_DIR, "old_test.dat")
        with open(old_mmap, 'w') as f: f.write("old mmap")
        # Artificially age the mmap file
        old_ts = (datetime.now() - timedelta(days=5)).timestamp()
        os.utime(old_mmap, (old_ts, old_ts))

        logger.info("Dummy files created. Running purge...")

        # 2. Run Purge (Keep 2 days)
        await sm.purge_old_snapshots(keep_days=2)

        # 3. Verify results
        assert not os.path.exists(old_file), "Old snapshot should have been deleted."
        assert os.path.exists(new_file), "New snapshot should remain."
        assert not os.path.exists(old_mmap), "Old memmap file should have been deleted."
        
        logger.info("✅ Verified: Old files deleted, new files preserved.")
        logger.info("✅ Subtask 5.6: Graph Eviction logic Verified.")

    finally:
        # Cleanup
        for f in [old_file, new_file, old_mmap]:
            if os.path.exists(f): os.remove(f)
        if os.path.exists("test_snapshots"):
            import shutil
            shutil.rmtree("test_snapshots")

if __name__ == "__main__":
    asyncio.run(test_snapshot_purging())
