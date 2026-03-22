import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Tuple

from services.search_service import SearchService
from database.session import SessionLocal, SessionTransit
from core.container import container
from services.multi_layer_cache import multi_layer_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("routemaster.warmup")

# Top 100 High-Traffic Station Pairs (Sample - Should be derived from analytics later)
TOP_PAIRS = [
    ("NDLS", "BCT"), ("NDLS", "HWH"), ("MAS", "SBC"), ("NDLS", "PNBE"), 
    ("CNB", "NDLS"), ("HWH", "NDLS"), ("BCT", "NDLS"), ("PNBE", "NDLS"),
    ("ADI", "BCT"), ("BCT", "ADI"), ("SBC", "MAS"), ("LKO", "NDLS"),
    # Add more as needed...
]

async def warm_cache():
    """
    Task 19: Cache Warming Script.
    Fills Redis with optimized results for the most popular routes.
    Prevents cold-start delays for 90% of common users.
    """
    logger.info("🔥 Starting Cache Warming Cycle...")
    start_time = time.time()
    
    # 1. Initialize Core Services
    await multi_layer_cache.initialize()
    db = SessionLocal()
    search_svc = SearchService(db)
    
    # 2. Iterate through Top Pairs for next 7 days
    dates = [datetime.now() + timedelta(days=i) for i in range(1, 4)] # Next 3 days prime
    
    count = 0
    tasks = []
    
    for src, dst in TOP_PAIRS:
        for d in dates:
            date_str = d.strftime("%Y-%m-%d")
            logger.info(f"⚡ Warming: {src} -> {dst} on {date_str}")
            
            # Use search_svc directly to trigger full caching logic
            tasks.append(search_svc.search_routes(
                source=src, destination=dst, travel_date=date_str, 
                limit=15, quota="GN"
            ))
            count += 1
            
            # Batch execution to avoid CPU spike
            if len(tasks) >= 3:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []
                await asyncio.sleep(0.5) 

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    duration = time.time() - start_time
    logger.info(f"✅ Cache Warming Complete. Processed {count} routes in {duration:.2f}s.")
    db.close()

if __name__ == "__main__":
    asyncio.run(warm_cache())
