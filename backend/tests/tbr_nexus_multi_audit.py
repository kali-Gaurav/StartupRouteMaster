
import asyncio
import logging
import time
from datetime import datetime
import os
import sys

sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.tbr_router import TripBasedRouter
from core.route_engine.snapshot_manager import SnapshotManager
from core.route_engine.graph import TimeDependentGraph
from core.route_engine.constraints import RouteConstraints
from database.session import initialize_database_pools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit.tbr.nexus")

async def run_multi_pair_audit():
    await initialize_database_pools()
    manager = SnapshotManager()
    snapshot = await manager.load_snapshot(datetime(2026, 3, 30))
    if not snapshot:
         print("❌ Snapshot load failed.")
         return
    graph = TimeDependentGraph(snapshot=snapshot)
    
    router = TripBasedRouter(max_transfers=3)
    constraints = RouteConstraints(max_transfers=3, range_minutes=1440)
    
    # Corrected IDs from Database Verification
    pairs = [
        ("MAS", "SBC", 4736, 6902, "High Freq"),
        ("NDLS", "CSMT", 5533, 1778, "Backbone"),
        ("HWH", "MAS", 3099, 4736, "Long Coast"),
        ("PNBE", "SBC", 6196, 6902, "Cross-Country"),
        ("GHY", "CSMT", 2567, 1778, "Extreme Distance")
    ]
    
    print("\n🚀 [TBR NEXUS AUDIT] Starting Five-Pair Yield Verification\n" + "="*60)
    
    for name_src, name_dst, sid_src, sid_dst, p_type in pairs:
        print(f"🔍 Testing {name_src} -> {name_dst} ({p_type})...")
        start_ts = time.perf_counter()
        try:
            results = await router.find_routes(sid_src, sid_dst, datetime(2026, 3, 30, 8, 0), constraints, graph)
            duration_ms = (time.perf_counter() - start_ts) * 1000
            
            yield_0 = len([r for r in results if len(r.transfers) == 0])
            yield_1 = len([r for r in results if len(r.transfers) == 1])
            yield_2 = len([r for r in results if len(r.transfers) == 2])
            yield_3 = len([r for r in results if len(r.transfers) >= 3])
            
            print(f"✅ Yield: {len(results)} total [0T:{yield_0}, 1T:{yield_1}, 2T:{yield_2}, 3T:{yield_3}]")
            print(f"⏱️  Duration: {duration_ms:.2f}ms")
            if results:
                print(f"🏆 Best: {results[0].total_duration} mins")
        except Exception as e:
            print(f"❌ Error during search: {e}")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(run_multi_pair_audit())
