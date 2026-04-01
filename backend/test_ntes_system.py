import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta

from database.session import initialize_database_pools, init_db
from services.scraper_sentinel import scraper_sentinel
from providers.clients.ntes_scraper import NtesScraperClient
from services.scraper.ntes_sync_service import ntes_sync_service
from providers.gateway import provider_gateway

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_ntes")

async def setup_system():
    """Initialize all necessary core components."""
    logger.info("Initializing system components for testing...")
    
    # 1. Initialize Database Pools
    try:
        await initialize_database_pools()
        # Ensure the table is created
        await init_db(["train_running_status_cache"])
        logger.info("✅ Database initialized.")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False

    # 2. Start Scraper Sentinel
    try:
        await scraper_sentinel.start()
        logger.info("✅ Scraper Sentinel started.")
    except Exception as e:
        logger.error(f"❌ Scraper Sentinel failed to start: {e}")
        return False
        
    return True

async def test_scraper_direct():
    """Test the scraper directly with a known train."""
    print("\n--- Phase 1: Direct Scraper Test ---")
    client = NtesScraperClient()
    train_no = "12625" # Kerala Express
    
    # Use Yesterday for testing to ensure status exists (since server might be at 01:00 AM)
    test_date = date.today() - timedelta(days=1)
    logger.info(f"Scraping status for {train_no} on {test_date}...")
    res = await client.get_live_status(train_no, journey_date=test_date)
    
    if res:
        logger.info("✅ Scraper Success!")
        logger.info(f"   Station: {res.get('current_station')}")
        logger.info(f"   Delay: {res.get('delay_info')}")
        logger.info(f"   Platform: {res.get('platform')}")
        return res
    else:
        logger.error("❌ Scraper Failed to return data.")
        return None

async def test_sync_service(raw_data):
    """Test the sync service for DB and Cache persistence."""
    print("\n--- Phase 2: Sync Service Test ---")
    if not raw_data:
        logger.warning("Skipping Sync Test due to failed scraper.")
        return
    
    train_no = raw_data["train_no"]
    journey_date = date.fromisoformat(raw_data["journey_date"])
    
    logger.info(f"Syncing data for {train_no}...")
    success = await ntes_sync_service.upsert_status(train_no, journey_date, raw_data)
    
    if success:
        logger.info("✅ Sync successful to DB and Redis.")
        # Try to retrieve from cache
        cached = await ntes_sync_service.get_cached_status(train_no, journey_date)
        if cached:
            logger.info(f"✅ Cache retrieval successful: {cached.get('current_station')}")
        else:
            logger.error("❌ Cache retrieval failed after sync.")
    else:
        logger.error("❌ Sync service reported failure.")

async def test_gateway_integration():
    """Test the end-to-end integration via the ProviderGateway."""
    print("\n--- Phase 3: Gateway Integration Test ---")
    train_no = "12625"
    test_date = date.today() - timedelta(days=1)
    train_date = test_date.isoformat()
    
    logger.info(f"Fetching status via Gateway for {train_no} on {train_date}...")
    # This should hit the cache if Phase 2 was successful
    unified = await provider_gateway.get_live_status(train_no, train_date=train_date)
    
    if unified:
        logger.info(f"✅ Gateway Integration Successful!")
        logger.info(f"   Normalized Status: {unified.running_status}")
        logger.info(f"   Current Station: {unified.current_station_name}")
        logger.info(f"   Delay: {unified.delay_minutes} mins")
    else:
        logger.error("❌ Gateway failed to provide unified status.")

async def main():
    if not await setup_system():
        logger.critical("Aborting tests due to setup failure.")
        return

    try:
        raw = await test_scraper_direct()
        if raw:
            await test_sync_service(raw)
            await test_gateway_integration()
    except Exception as e:
        logger.error(f"Unexpected error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Graceful shutdown
        logger.info("Shutting down...")
        await provider_gateway.shutdown()
        await scraper_sentinel.stop()

if __name__ == "__main__":
    asyncio.run(main())
