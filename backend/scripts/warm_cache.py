import asyncio
import logging
import sys
import os
from datetime import datetime, date, timedelta

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import SessionTransit, SessionLocal
from services.search_service import SearchService
from services.multi_layer_cache import multi_layer_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cache_warmer")

TOP_ROUTES = [
    ("NDLS", "BCT"), ("NDLS", "MAS"), ("NDLS", "SBC"),
    ("PGT", "KOTA"), ("MAS", "SBC"), ("HWH", "NDLS"),
    ("ADI", "BCT"), ("PUNE", "BCT"), ("STA", "JBP")
]

async def warm_cache():
    logger.info("🚀 Starting Proactive Cache Warming...")
    await multi_layer_cache.initialize()
    
    db_user = SessionLocal()
    search_service = SearchService(db_user)
    
    # Dates: Today, Tomorrow, Day After
    dates = [date.today(), date.today() + timedelta(days=1), date.today() + timedelta(days=2)]
    personas = ["budget", "comfort"]
    
    count = 0
    for src, dst in TOP_ROUTES:
        for d in dates:
            for persona in personas:
                date_str = d.strftime("%Y-%m-%d")
                logger.info(f"  Warming: {src} -> {dst} on {date_str} ({persona})")
                try:
                    # This call automatically caches in multi_layer_cache
                    await search_service.search_routes(src, dst, date_str, budget_category=persona)
                    count += 1
                except Exception as e:
                    logger.error(f"  Failed to warm {src}->{dst}: {e}")
                
                await asyncio.sleep(0.1) # Be gentle

    db_user.close()
    logger.info(f"✅ Cache warming complete. Hydrated {count} combinations.")

if __name__ == "__main__":
    asyncio.run(warm_cache())
