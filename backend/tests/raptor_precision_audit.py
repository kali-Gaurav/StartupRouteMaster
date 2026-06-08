import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine import route_engine
from core.route_engine.constraints import RouteConstraints, DiscoveryModel
from database.infrastructure.session import initialize_database_pools, SessionTransit
from core.route_engine.base import RoutingRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit.precision")

async def run_precision_audit():
    await initialize_database_pools()
    
    from core.route_engine.snapshot_manager import SnapshotManager
    manager = SnapshotManager()
    # Use a known snapshot date
    snapshot_date = datetime(2026, 5, 4)
    snapshot = await manager.load_snapshot(snapshot_date)
    if not snapshot:
        logger.error("❌ Snapshot load failed. Run build_production_graph first.")
        return

    orchestrator = UnifiedRoutingOrchestrator(route_engine)
    
    # Test Case: Long distance with potential for pruning
    source, dest = "MAS", "NDLS" # Chennai to Delhi
    departure_time = datetime(2026, 5, 4, 8, 0)
    
    constraints = RouteConstraints(
        discovery_model=DiscoveryModel.OMNISCIENT,
        max_transfers=3,
        range_minutes=1440,
        discovery_only=True
    )
    
    logger.info(f"🔍 [PRECISION AUDIT] Running Search: {source} -> {dest}")
    
    with SessionTransit() as db:
        req = RoutingRequest(
            source_code=source,
            destination_code=dest,
            departure_date=departure_time,
            constraints=constraints,
            limit=50,
            db_session=db
        )
        
        start_ts = datetime.now()
        results = await orchestrator.search_all_tiers(req)
        duration = (datetime.now() - start_ts).total_seconds() * 1000
        
        # Check yield and variety
        if isinstance(results, dict):
            visible_yield = results.get("metadata", {}).get("visible_yield", 0)
            buckets = results.get("buckets", {})
            logger.info(f"📊 Yield: {visible_yield} routes in {duration:.2f}ms")
            for b_name, b_list in buckets.items():
                logger.info(f"   ├─ {b_name:15}: {len(b_list)}")
        else:
            logger.info(f"📊 Yield: {len(results)} routes in {duration:.2f}ms")

    logger.info("✅ Precision Audit Complete.")

if __name__ == "__main__":
    asyncio.run(run_precision_audit())
