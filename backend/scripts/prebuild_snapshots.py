import asyncio
import logging
import time
from datetime import datetime, timedelta
from database.session import SessionLocal
from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.graph import TimeDependentGraph
from core.redis import redis_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SnapshotPrebuilder")

async def prebuild_system():
    logger.info("🚀 STARTING PRODUCTION PRE-BUILD SEQUENCE")
    engine = RailwayRouteEngine()
    
    # Pre-build for next 7 days
    start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(7):
        target_date = start_date + timedelta(days=i)
        date_str = target_date.strftime('%Y-%m-%d')
        logger.info(f"--- Processing Day {i+1}/7: {date_str} ---")
        
        # 1. Build Graph Snapshot
        logger.info(f"Building StaticGraphSnapshot for {date_str}...")
        start_time = time.time()
        # This will build, save to disk, and push to Redis automatically via our upgraded SnapshotManager
        graph = await engine._get_current_graph(target_date)
        duration = time.time() - start_time
        logger.info(f"✅ Graph Ready: {len(graph.snapshot.stop_cache)} stops, {len(graph.snapshot.trip_segments)} trips in {duration:.2f}s")
        
        # 2. Pre-compute Hub Connectivity Table
        logger.info(f"Pre-computing Hub Connectivity for {date_str}...")
        hub_start = time.time()
        # The engine normally does this lazily; we force it here
        hub_table = await engine.hub_manager.precompute_hub_connectivity(graph, target_date)
        engine.raptor.set_hub_table(hub_table)
        hub_duration = time.time() - hub_start
        logger.info(f"✅ Hub Table Ready: {len(hub_table.reachable_hubs)} entries in {hub_duration:.2f}s")
        
        # 3. Warm up Station Cache in Redis
        logger.info("Warming up station metadata cache...")
        from services.station_service import StationService
        db = SessionLocal()
        station_service = StationService(db)
        # Simply calling a broad search will trigger the Redis caching logic we implemented
        station_service.search_stations_by_name("A") 
        station_service.search_stations_by_name("B")
        db.close()

    logger.info("="*60)
    logger.info("🏁 PRE-BUILD COMPLETE: System is now optimized for instant search.")
    logger.info("="*60)

if __name__ == "__main__":
    asyncio.run(prebuild_system())
