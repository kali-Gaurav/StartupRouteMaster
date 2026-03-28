
import asyncio
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from core.route_engine.snapshot_manager import SnapshotManager
from datetime import datetime

async def main():
    sm = SnapshotManager()
    # Try to see if ANY snapshot exists
    # SnapshotManager saves to backend/data/snapshots/
    snap_dir = os.path.join(os.getcwd(), 'backend', 'data', 'snapshots')
    if os.path.exists(snap_dir):
        files = os.listdir(snap_dir)
        print(f"Snapshots found: {files}")
    else:
        print("Snapshot directory not found.")
    
    sn = await sm.load_snapshot(datetime.now())
    if sn:
        print(f"Loaded snapshot date: {sn.date}")
    else:
        print("No snapshot loaded for today.")

if __name__ == "__main__":
    asyncio.run(main())
