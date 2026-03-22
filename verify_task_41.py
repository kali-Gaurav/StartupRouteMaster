import asyncio
import logging
from datetime import datetime
from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.graph import TimeDependentGraph
from core.route_engine.snapshot_manager import SnapshotManager
from core.route_engine.constraints import RouteConstraints
from database.session import SessionLocal
from database.models import Stop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_performance():
    # 1. Setup
    snapshot_manager = SnapshotManager()
    departure_date = datetime(2026, 3, 20) # Use a future date
    snapshot = snapshot_manager.load_snapshot_sync(departure_date)
    if not snapshot:
        logger.error("Snapshot not found. Please run builder first.")
        return
    
    graph = TimeDependentGraph(snapshot=snapshot)
    raptor = OptimizedRAPTOR(max_transfers=2)
    
    # 2. Define test case (e.g., NDLS to HWH)
    # NDLS ID: 5533, HWH ID: 3099 (from previous check)
    source_id = 5533
    dest_id = 3099
    
    constraints = RouteConstraints(max_results=10)
    
    logger.info(f"Starting search from {source_id} to {dest_id}")
    
    # 3. Execute
    start_time = datetime.now()
    routes = await raptor.find_routes(source_id, dest_id, departure_date, constraints, graph)
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    
    logger.info(f"Search completed in {duration:.2f}s")
    logger.info(f"Found {len(routes)} routes.")
    
    for i, r in enumerate(routes[:3]):
        logger.info(f"Route {i+1}: {len(r.segments)} segments, {r.total_duration} mins, {r.total_distance:.1f} km")
        for s in r.segments:
            logger.info(f"  - Train {s.train_number}: {s.departure_stop_id} -> {s.arrival_stop_id} ({s.departure_time} to {s.arrival_time})")

if __name__ == "__main__":
    asyncio.run(verify_performance())
