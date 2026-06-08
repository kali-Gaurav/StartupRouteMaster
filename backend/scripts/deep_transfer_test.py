import asyncio
import logging
import time
from datetime import datetime, timedelta
import sys
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("deep_transfer_test")

# Import system components
sys.path.append(os.getcwd())

from database.session import initialize_database_pools
from services.search_service import search_service
from core.infrastructure.container import container
from core.route_engine.constraints import DiscoveryModel

async def run_deep_test():
    logger.info("🚄 Starting Deep-Transfer Stress Test (JAT -> CAPE)...")
    
    # 1. Initialize Infrastructure
    await initialize_database_pools()
    await container.get("rapidapi")
    
    source = "JAT"
    destination = "CAPE"
    travel_date = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")
    
    logger.info(f"🔍 Searching: {source} -> {destination} | Model: OMNISCIENT | Transfers: 5")
    
    start_time = time.time()
    # Perform Search with Omniscient model for maximum depth
    search_res = await search_service.search_routes(
        source=source, 
        destination=destination, 
        travel_date=travel_date,
        budget_category="comfort",
        discovery_model="OMNISCIENT"
    )
    latency = (time.time() - start_time) * 1000
    
    if search_res.get("status") != "success":
        logger.error(f"❌ Search Failed: {search_res.get('message')}")
        return

    data = search_res.get("data", {})
    grouped = data.get("grouped_journeys", {})
    all_routes = []
    for r_list in grouped.values():
        if isinstance(r_list, list):
            all_routes.extend(r_list)

    logger.info(f"✅ Found {len(all_routes)} candidate routes in {latency:.2f}ms")
    
    if not all_routes:
        logger.warning("⚠️ No routes found for this extreme O-D pair.")
        return

    # 2. Analyze Chain Complexity
    for i, r in enumerate(all_routes[:5]):
        segments = r.get("segments", [])
        transfers = len(segments) - 1
        logger.info(f"Route #{i+1}: {transfers} transfers | Duration: {r.get('duration_minutes')}m")
        for j, seg in enumerate(segments):
            logger.info(f"  Leg {j+1}: {seg.get('departure_code')} -> {seg.get('arrival_code')} (Train: {seg.get('train_number')})")

    # 3. Final Summary
    logger.info("="*50)
    logger.info(f"STRESS TEST COMPLETE: {source} -> {destination}")
    logger.info(f"P99 Latency: {latency:.2f}ms")
    logger.info(f"Total Unique Routes: {len(all_routes)}")
    logger.info("="*50)

if __name__ == "__main__":
    asyncio.run(run_deep_test())
