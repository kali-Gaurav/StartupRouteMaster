import logging
import asyncio
from celery import shared_task
from datetime import date, datetime

from providers.clients.ntes_scraper import NtesScraperClient
from services.scraper.ntes_sync_service import ntes_sync_service
from core.redis import async_redis_client, resource_lock

logger = logging.getLogger("scraper.tasks")

@shared_task(name="scraper.scrape_train_status", bind=True, max_retries=2)
def scrape_train_status(self, train_no: str, journey_date_str: str):
    """
    [Task 48.13] Distributed Scraper Task with Redlock Protection.
    Ensures only ONE worker node scrapes the same train at a time.
    """
    try:
        journey_date = datetime.strptime(journey_date_str, "%Y-%m-%d").date()
        lock_key = f"scrape_lock:{train_no}:{journey_date_str}"
        
        # Event Loop for Async logic within sync Celery task
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        async def run_protected_scrape():
            # 1. Acquire Distributed Lock (Task 48.13)
            async with resource_lock(lock_key, lease_time=60, wait_time=5) as acquired:
                if not acquired:
                    logger.warning(f"🔒 [WORKER] Scrape for {train_no} already in progress elsewhere. Skipping.")
                    return "IN_PROGRESS"

                # 2. Double-Check Cache (Did another worker just finish?)
                cached = await ntes_sync_service.get_cached_status(train_no, journey_date)
                if cached:
                    logger.info(f"💾 [WORKER] Cache fulfilled by another worker for {train_no}. Aborting redundant scrape.")
                    return "FULFILLED"

                # 3. Execute Scrape
                client = NtesScraperClient()
                try:
                    logger.info(f"🚀 [WORKER] Executing Atomic Scrape for {train_no}...")
                    res = await client.get_live_status(train_no, journey_date=journey_date)
                    
                    if res:
                        await ntes_sync_service.upsert_status(train_no, journey_date, res)
                        return "SUCCESS"
                    return "NO_DATA"
                finally:
                    await client.close_playwright()

        result = loop.run_until_complete(run_protected_scrape())
        return result

    except Exception as e:
        logger.error(f"❌ [WORKER] Critical failure in scraper task: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(name="scraper.prewarm_high_priority_trains")
def prewarm_high_priority_trains():
    """
    [Task 50.1] Periodically scrapes status for important trains.
    To be called via Celery Beat.
    """
    # Logic to fetch high-priority trains from DB and trigger individual scrapes
    pass
