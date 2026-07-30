
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
logger = logging.getLogger("audit.tbr")

async def run_tbr_audit():
    await initialize_database_pools()
    manager = SnapshotManager()
    snapshot = await manager.load_snapshot(datetime(2026, 3, 30))
    if not snapshot:
         print("❌ Snapshot load failed.")
         return
    graph = TimeDependentGraph(snapshot=snapshot)
    
    router = TripBasedRouter(max_transfers=2)
    constraints = RouteConstraints(max_transfers=2, range_minutes=1440)
    
    # MAS (Chennai) -> SBC (Bangalore)
    start_ts = time.perf_counter()
    results = await router.find_routes(5533, 3099, datetime(2026, 3, 30, 8, 0), constraints, graph)
    end_ts = time.perf_counter()
    
    print(f"📊 [TBR AUDIT] Yield: {len(results)} routes")
    print(f"📊 [TBR AUDIT] Duration: {(end_ts - start_ts) * 1000:.2f}ms")
    
    if results:
        print(f"🏆 Best Route Duration: {results[0].total_duration} mins")

if __name__ == "__main__":
    asyncio.run(run_tbr_audit())
