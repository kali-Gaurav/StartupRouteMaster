
import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from database.session import SessionLocal
from database.config import Config
from services.station_service import StationService
from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
from core.redis import redis_client

# Set up specific logging to see internal transitions
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("SurgicalTest")

async def verify_system_workflow():
    logger.info("Starting Surgical Workflow Verification...")
    
    # 1. Verify Configuration & Env
    logger.info(f"Config ENVIRONMENT: {Config.ENVIRONMENT}")
    logger.info(f"Config RAPIDAPI_KEY exists: {bool(Config.RAPIDAPI_KEY)}")
    logger.info(f"Config REDIS_URL exists: {bool(Config.REDIS_URL)}")
    
    db = SessionLocal()
    station_service = StationService(db)
    engine = RailwayRouteEngine()
    
    try:
        # 2. Station Resolution (Workflow Step 1)
        src_query = "ABU ROAD"
        dst_query = "AHMEDABAD"
        
        src_stations = station_service.search_stations_by_name(src_query)
        dst_stations = station_service.search_stations_by_name(dst_query)
        
        if not src_stations or not dst_stations:
            logger.error(f"Station resolution failed! Src: {len(src_stations)}, Dst: {len(dst_stations)}")
            return
            
        src = src_stations[0]
        dst = dst_stations[0]
        logger.info(f"Resolved: {src['name']} ({src['code']}) -> {dst['name']} ({dst['code']})")

        # 3. Graph Building (Workflow Step 2)
        target_date = datetime.now() + timedelta(days=7) # Next week
        target_date = target_date.replace(hour=10, minute=0, second=0, microsecond=0)
        
        logger.info(f"Building/Loading Graph for {target_date.date()}...")
        graph_start = datetime.now()
        graph = await engine._get_current_graph(target_date)
        graph_end = datetime.now()
        
        logger.info(f"Graph Ready in {(graph_end - graph_start).total_seconds()}s")
        logger.info(f"Stops in memory: {len(graph.stop_cache)}")
        logger.info(f"Trips in memory: {len(graph.trip_segments)}")

        # 4. Route Search (Workflow Step 3)
        constraints = RouteConstraints(max_transfers=1)
        
        logger.info("Executing RAPTOR search...")
        search_start = datetime.now()
        routes = await engine.search_routes(src['code'], dst['code'], target_date, constraints=constraints)
        search_end = datetime.now()
        
        logger.info(f"Search completed in {(search_end - search_start).total_seconds()}s")
        logger.info(f"Routes found: {len(routes)}")

        # 5. Verify Redis Caching
        cache_key = f"search:{src['code']}:{dst['code']}:{target_date.strftime('%Y-%m-%d')}:*"
        # Note: In production SearchService uses a more complex key, but let's check keys in redis
        keys = redis_client.keys("search:*")
        logger.info(f"Redis Search Cache Keys: {len(keys)}")

        # 6. Verify RapidAPI Integration (if online)
        if engine.data_provider.has_live_fares:
            logger.info("Live API Integration: ACTIVE")
        else:
            logger.info("Live API Integration: INACTIVE (Falling back to DB/Offline)")

        # 7. Output Result Summary
        if routes:
            for i, r in enumerate(routes[:1]):
                logger.info(f"Sample Route Found: {r.total_duration} mins, {len(r.segments)} segments")
        else:
            # DEBUG: Check if there are ANY departures from source
            deps = graph.get_departures_from_stop(src['id'], target_date)
            logger.info(f"Total departures from {src['code']} in next 24h: {len(deps)}")
            if deps:
                logger.info(f"Sample Departure from Source: {deps[0]}")

    except Exception as e:
        logger.error(f"Workflow Exception: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_system_workflow())
