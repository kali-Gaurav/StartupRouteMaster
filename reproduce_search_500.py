import asyncio
import os
import sys
import logging
from datetime import datetime

# Mock pandas and pendulum
import sys
from unittest.mock import MagicMock
sys.modules["pandas"] = MagicMock()
sys.modules["pendulum"] = MagicMock()

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# --- CRITICAL: Binary Environment Patch ---
# numpy/pydantic-core reads datetime.datetime_CAPI during its own C-ext init.
import datetime as _dt_patch
import _datetime as _dt_capi
if not hasattr(_dt_patch, 'datetime_CAPI') and hasattr(_dt_capi, 'datetime_CAPI'):
    setattr(_dt_patch, 'datetime_CAPI', _dt_capi.datetime_CAPI)
del _dt_patch, _dt_capi 

# Mock environment

from services.search_service import SearchService
from database.session import SessionTransit
from services.jit_manager import jit_manager

async def reproduce():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("repro")

    # 1. Initialize JIT Nodes
    from app import load_database, load_cache, load_route_engine
    jit_manager.register_node("DATABASE", [], load_database)
    jit_manager.register_node("CACHE", [], load_cache)
    jit_manager.register_node("GRAPH", ["DATABASE", "CACHE"], load_route_engine)

    logger.info("Initializing JIT nodes...")
    await jit_manager.ensure_ready("GRAPH")
    logger.info("JIT Ready.")

    # 2. Call Search Service
    db = SessionTransit()
    service = SearchService(db)
    
    try:
        logger.info("Starting search MMCT -> NDLS...")
        result = await service.search_routes(
            source="MMCT",
            destination="NDLS",
            travel_date=datetime.now().strftime("%Y-%m-%d"),
            budget_category="comfort",
            limit=5
        )
        logger.info(f"Search Completed. Found {len(result.get('journeys', []))} journeys.")
    except Exception as e:
        logger.error(f"Search Failed with 500-equivalent exception: {type(e).__name__}: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(reproduce())
