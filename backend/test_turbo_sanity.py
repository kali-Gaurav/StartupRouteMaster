import asyncio
import logging
from datetime import datetime
from core.route_engine.turbo_router import TurboRouter
from database.session import initialize_database_pools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("turbo_checker")

async def test_performance():
    logger.info("🚀 Initializing Database Pools...")
    await initialize_database_pools()
    
    router = TurboRouter()
    
    # NDLS (New Delhi) to BCT (Mumbai Central)
    src = "NDLS"
    dst = "BCT"
    date = datetime(2026, 4, 1) # A Wednesday
    
    logger.info(f"🔍 Searching routes from {src} to {dst} on {date.date()}...")
    start = time.time()
    routes = await router.find_routes(src, dst, date, limit=5)
    end = time.time()
    
    logger.info(f"⏱️ Search completed in {(end - start)*1000:.2f}ms")
    logger.info(f"📦 Found {len(routes)} routes.")
    
    for i, r in enumerate(routes):
        if r['type'] == 'direct':
            logger.info(f"  {i+1}. [DIRECT] Train {r['train_no']} | Dep: {r['dep']} | Arr: {r['arr']} | Dur: {r['duration']}m")
        else:
            logger.info(f"  {i+1}. [TRANSFER] Hub: {r['hub']} | Leg1: {r['legs'][0]['train']} -> Leg2: {r['legs'][1]['train']} | Dur: {r['duration']}m")

if __name__ == "__main__":
    import time
    asyncio.run(test_performance())
