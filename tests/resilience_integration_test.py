import asyncio
import logging
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from backend.providers.gateway import provider_gateway
from backend.providers.clients.rapidapi import RapidApiClient
from backend.providers.clients.ntes_scraper import NtesScraperClient
from backend.database.session import AsyncSessionUser, init_db
from backend.database.models import APIBudget

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test.resilience")

async def test_failover_and_budget():
    logger.info("🧪 Starting Resilience Integration Test...")
    await init_db()
    
    # 1. Initialize Budget in DB if not exists
    async with AsyncSessionUser() as session:
        from sqlalchemy import select
        existing = await session.execute(select(APIBudget).where(APIBudget.provider_name == "RapidAPI"))
        budget = existing.scalar_one_or_none()
        if not budget:
            budget = APIBudget(
                provider_name="RapidAPI",
                monthly_limit=500.0,
                current_spend=0.0,
                cost_per_request=0.01
            )
            session.add(budget)
            await session.commit()
            logger.info("✅ RapidAPI budget initialized.")
        else:
            # Reset spend for test
            budget.current_spend = 0.0
            await session.commit()
            logger.info("✅ RapidAPI budget reset to 0.0.")

    # 2. Test Successful RapidAPI call -> Budget should increase
    logger.info("📡 Testing successful RapidAPI call...")
    # NOTE: provider_gateway.get_live_status will call _record_api_cost in background
    # For the test, we will just wait and check.
    status = await provider_gateway.get_live_status("12001", "2026-03-24")
    
    # We call it manually to be sure it happens in this thread/loop for the test
    # await provider_gateway._record_api_cost("RapidAPI") 
    
    await asyncio.sleep(5) # Wait for background cost recording task
    
    async with AsyncSessionUser() as session:
        budget = (await session.execute(select(APIBudget).where(APIBudget.provider_name == "RapidAPI"))).scalar_one()
        logger.info(f"📊 Current Spend after 1 call: {budget.current_spend}")
        assert budget.current_spend > 0.0, "Budget did not decrement!"

    # 3. Simulate RapidAPI Failure -> Failover to NTES
    logger.info("🚧 Simulating RapidAPI failure...")
    # Force budget to be 'not ok' OR mock the _safe_fetch_rapidapi to fail
    original_is_budget_ok = provider_gateway._is_budget_ok
    provider_gateway._is_budget_ok = lambda name: asyncio.Future().set_result(False) if name == "RapidAPI" else asyncio.Future().set_result(True)
    
    # Overriding with a lambda that returns a coroutine/future
    async def mock_budget_fail(name): return False
    provider_gateway._is_budget_ok = mock_budget_fail

    logger.info("🔎 Testing failover to NTES Scraper...")
    status_failover = await provider_gateway.get_live_status("12002", "2026-03-24")
    
    if status_failover and status_failover.data_source == "ntes_scraper":
        logger.info("✅ Failover successful! Data source: ntes_scraper")
    else:
        logger.error(f"❌ Failover failed or source mismatch: {status_failover.data_source if status_failover else 'None'}")

    # 4. Cleanup
    provider_gateway._is_budget_ok = original_is_budget_ok
    await provider_gateway.ntes_client.close_playwright()
    logger.info("🏁 Resilience Test Completed.")

if __name__ == "__main__":
    asyncio.run(test_failover_and_budget())
