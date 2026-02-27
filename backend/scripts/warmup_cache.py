import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("warmup_cache")

COMMON_PAIRS = [
    ("NDLS", "BCT"),
    ("MAS", "SBC"),
    ("HWH", "NDLS"),
    ("ADI", "BCT"),
    ("NDLS", "ADI"),
    ("BCT", "NDLS")
]

async def warmup():
    engine = RailwayRouteEngine()
    
    today = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    dates = [today + timedelta(days=i) for i in range(3)]
    
    constraints = RouteConstraints(max_transfers=1)
    
    for target_date in dates:
        logger.info(f"--- Warming up cache for {target_date.date()} ---")
        for src, dst in COMMON_PAIRS:
            logger.info(f"Searching {src} -> {dst}")
            try:
                # search_routes already handles caching internally via SearchService calling it
                # or here we call it directly on the engine.
                # OptimizedRAPTOR.find_routes handles the cache.
                await engine.search_routes(src, dst, target_date, constraints=constraints)
                logger.info(f"Cached {src} -> {dst}")
            except Exception as e:
                logger.error(f"Failed to cache {src} -> {dst}: {e}")

if __name__ == "__main__":
    asyncio.run(warmup())
