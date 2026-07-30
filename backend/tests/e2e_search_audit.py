
import asyncio
import logging
import json
from datetime import datetime, timedelta
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine import route_engine
from core.route_engine.graph import TimeDependentGraph
from core.route_engine.constraints import RouteConstraints
from database.session import initialize_database_pools, SessionTransit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit.search")

async def run_audit():
    await initialize_database_pools()
    
    # 1. Load Snapshot (v10.0 Spine) via Optimized Manager
    from core.route_engine.snapshot_manager import SnapshotManager
    from core.route_engine import route_engine
    
    manager = SnapshotManager()
    snapshot = await manager.load_snapshot(datetime(2026, 3, 30))
    if not snapshot:
        logger.error("❌ Snapshot load failed. Run build_production_graph first.")
        return

    graph = TimeDependentGraph(snapshot=snapshot)
    orchestrator = UnifiedRoutingOrchestrator(route_engine)
    
    # [Task 121] TEST CASE 1: Chennai -> Bangalore (Inter-City)
    source, dest = "MAS", "SBC"
    departure_time = datetime(2026, 3, 30, 8, 0)
    
    # [Task 121: Elastic Constraints]
    constraints = RouteConstraints(
        max_transfers=2,
        preferred_class="SL",
        range_minutes=1440 # 24h window
    )
    # [Task 10] Discovery skip heavy hydration for raw search speed test
    setattr(constraints, 'discovery_only', True)
    
    logger.info(f"🔍 [AUDIT] Running E2E Search: {source} -> {dest} at {departure_time}")
    
    start_ts = datetime.now()
    results = await orchestrator.search_all_tiers(
        source, dest, departure_time, constraints
    )
    duration = (datetime.now() - start_ts).total_seconds() * 1000
    
    logger.info(f"📊 Audit Yield: {len(results)} routes found in {duration:.2f}ms")
    
    # Group results by engine
    stats = {}
    for r in results:
        engine = r.metadata.get("engine", "unknown")
        stats[engine] = stats.get(engine, 0) + 1
        
    for eng, count in stats.items():
        logger.info(f"   ├─ Engine: {eng:15} | Count: {count}")

    if results:
        best = results[0]
        logger.info(f"🏆 BEST ROUTE: {best.journey_id}")
        for i, seg in enumerate(best.segments):
            logger.info(f"   [{i+1}] Train {seg.train_number} ({seg.departure_code} -> {seg.arrival_code})")
            logger.info(f"       DEP: {seg.departure_time} | ARR: {seg.arrival_time}")

if __name__ == "__main__":
    asyncio.run(run_audit())
