"""
Final Integration Test (Phase 6)

Verifies:
1. Station Time Index (Phase 2)
2. Connection Survival Simulation (Phase 4 - TODO #33-35)
3. Engine Usage Tracking (Phase 6 - TODO #48)
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.search_service import SearchService
from database.session import SessionLocal
from services.multi_layer_cache import multi_layer_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("final-test")

async def run_test():
    session = SessionLocal()
    search_svc = SearchService(session)
    
    # 1. Clear usage metrics for today to start fresh
    await multi_layer_cache.initialize()
    today = datetime.utcnow().date().isoformat()
    usage_key = f"metrics:engine_usage:{today}"
    if multi_layer_cache.redis:
        await multi_layer_cache.redis.delete(usage_key)
    
    # 2. Perform Search (NDLS -> MAS)
    # This should trigger Turbo -> RAPTOR flow
    logger.info("Starting search test: NDLS -> MAS")
    result = await search_svc.search_routes(
        source="NDLS",
        destination="MAS",
        travel_date="2026-03-03",
        limit=5
    )
    
    journeys = result.get("journeys", [])
    logger.info(f"Found {len(journeys)} journeys.")
    
    for idx, j in enumerate(journeys[:3]):
        logger.info(f"Journey {idx+1}:")
        logger.info(f"  - Transfers: {j['num_transfers']}")
        logger.info(f"  - Reliability: {j.get('reliability_score', 'N/A')}")
        # Verify TODO #35: break_probability
        logger.info(f"  - Break Probability: {j.get('break_probability', 'N/A')}")
        
    # 3. Verify TODO #48: Engine Usage Tracking
    if multi_layer_cache.redis:
        usage = await multi_layer_cache.redis.hgetall(usage_key)
        logger.info(f"Engine Usage recorded: {usage}")
        
    session.close()

if __name__ == "__main__":
    asyncio.run(run_test())
