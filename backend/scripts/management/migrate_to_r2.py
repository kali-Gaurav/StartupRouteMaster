import asyncio
import sys
import os
from pathlib import Path

# Set project root to PYTHONPATH
backend_dir = Path(__file__).parent.absolute()
sys.path.append(str(backend_dir))

from services.storage_sync import r2_sync_manager

async def main():
    print("🚀 Starting Cloudflare R2 Data Migration...")
    
    # List of critical data to sync for Nexus Fiber
    paths_to_sync = [
        "database/user_store.db",
        "database/transit_graph.db",
        "database/railway_data.db",
        "snapshots/graph_snapshot_20260328.pkl",
        "snapshots/graph_snapshot_20260330.pkl",
        "nexus_vitals.mmap"
    ]
    
    for rel_path in paths_to_sync:
        print(f"📦 Processing {rel_path}...")
        success = await r2_sync_manager.sync_to_r2(rel_path)
        if success:
            print(f"✅ Successfully synced {rel_path} to Cloudflare R2.")
        else:
            print(f"❌ Failed to sync {rel_path}. Check logs.")

if __name__ == "__main__":
    asyncio.run(main())
