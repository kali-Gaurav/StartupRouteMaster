import asyncio
import time
import logging
import sys
import os
from datetime import datetime

# Adjust path to include the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.route_engine.engine import RailwayRouteEngine
from backend.services.multi_layer_cache import multi_layer_cache
from backend.core.route_engine.graph import RealtimeOverlay

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RedisPerformanceTest")

async def test_redis_snapshot_sync():
    """Verify that a snapshot saved in Redis can be retrieved quickly."""
    engine = RailwayRouteEngine()
    date = datetime(2025, 5, 20)
    
    logger.info(f"--- Testing Redis Snapshot Sync for {date.date()} ---")
    
    # 1. Force a build and save (this will go to Redis)
    start_time = time.time()
    graph = await engine.graph_builder.build_graph(date)
    build_time = time.time() - start_time
    logger.info(f"Initial Graph Build + Redis Save: {build_time:.2f}s")
    
    # 2. Extract snapshot and verify it exists in Redis
    date_str = date.strftime('%Y%m%d')
    await multi_layer_cache.initialize()
    cached_snapshot = await multi_layer_cache.get_graph_snapshot(date_str)
    
    if cached_snapshot:
        logger.info(f"✅ Redis Cache Hit: Snapshot for {date_str} found and decompressed.")
        logger.info(f"   Snapshot Version: {getattr(cached_snapshot, 'version', 'unknown')}")
    else:
        logger.error("❌ Redis Cache Miss: Snapshot not found in Redis.")
        return

    # 3. Simulate a fresh engine loading from Redis
    new_engine = RailwayRouteEngine()
    start_time = time.time()
    loaded_snapshot = await new_engine.snapshot_manager.load_snapshot(date)
    load_time = time.time() - start_time
    
    if loaded_snapshot:
        logger.info(f"✅ Fast Load from Redis: {load_time*1000:.2f}ms")
        if load_time < 0.5: # Goal is sub-500ms for 200MB graph via Redis + Zlib
             logger.info("⚡ Performance Goal Met: Sub-500ms loading!")
        else:
             logger.warning(f"⚠️ Performance Load Time: {load_time*1000:.2f}ms (Exceeds 500ms goal)")
    else:
        logger.error("❌ Failed to load snapshot in new engine.")

async def test_overlay_distributed_sync():
    """Verify that delay updates in one processor are visible to the engine via Redis."""
    engine = RailwayRouteEngine()
    
    logger.info("\n--- Testing Distributed Realtime Overlay Sync ---")
    
    # Simulate an external processor pushing a delay
    from backend.core.realtime_event_processor import RealtimeEventProcessor
    processor = RealtimeEventProcessor(engine)
    
    test_trip_id = 9999
    test_delay = 45
    
    updates = [{
        'trip_id': test_trip_id,
        'delay_minutes': test_delay,
        'train_number': "TEST-TRAIN-123"
    }]
    
    logger.info(f"Simulating event processor pushing {test_delay}min delay for trip {test_trip_id}...")
    # NOTE: This uses the session which might fail if DB isn't set up, but we focus on the call flow
    try:
        from backend.database import SessionLocal
        session = SessionLocal()
        await processor._apply_updates_to_overlay(session, updates)
        session.close()
    except Exception as e:
        logger.warning(f"Minor: DB update failed during test, but Redis push may have worked: {e}")

    # Now simulate a DIFFERENT engine syncing from Redis
    engine_2 = RailwayRouteEngine()
    await engine_2.sync_realtime_overlay()
    
    synced_delay = engine_2.current_overlay.get_trip_delay(test_trip_id)
    if synced_delay == test_delay:
        logger.info(f"✅ Distributed Sync Success: Engine 2 sees {synced_delay}min delay via Redis!")
    else:
        logger.error(f"❌ Distributed Sync Failed: Engine 2 sees {synced_delay}min instead of {test_delay}min.")

async def main():
    await test_redis_snapshot_sync()
    await test_overlay_distributed_sync()

if __name__ == "__main__":
    asyncio.run(main())
