
import asyncio
import logging
from datetime import datetime
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine import route_engine
from database.session import initialize_database_pools, SessionTransit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit.tier0")

async def run_tier0_test():
    await initialize_database_pools()
    orchestrator = UnifiedRoutingOrchestrator(route_engine)
    
    source_id, dest_id = 4736, 6902 # MAS, SBC
    departure_time = datetime(2026, 3, 30, 8, 0)
    
    db = SessionTransit()
    try:
        logger.info(f"🔍 Testing Tier 0 (Hub Backbone) directly: {source_id} -> {dest_id}")
        results = await orchestrator._search_tier_0_hubs_async(source_id, dest_id, departure_time, db)
        logger.info(f"📊 Yield: {len(results)} routes.")
        
        for r in results[:3]:
            logger.info(f"   Route: {r.segments[0].train_number} DEP: {r.segments[0].departure_time}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_tier0_test())
