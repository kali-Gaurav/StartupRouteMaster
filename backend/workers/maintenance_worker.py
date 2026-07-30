import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from database.session import engine_user, engine_transit

logger = logging.getLogger("maintenance-worker")

async def run_db_optimization():
    """
    Performs VACUUM and ANALYZE on both SQLite databases (TODO #23).
    """
    logger.info("📅 Starting Nightly Database Optimization...")
    
    for name, engine in [("UserStore", engine_user), ("TransitGraph", engine_transit)]:
        try:
            logger.info(f"Optimizing {name}...")
            with engine.connect() as conn:
                # 1. ANALYZE (Updates statistics for the query planner)
                conn.execute(text("ANALYZE"))
                # 2. VACUUM (Rebuilds the database file, reclaiming space)
                # Note: VACUUM cannot be run inside a transaction block in some versions
                conn.execution_options(isolation_level="AUTOCOMMIT").execute(text("VACUUM"))
            logger.info(f"✅ {name} optimized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to optimize {name}: {e}")

def start_worker():
    scheduler = AsyncIOScheduler()
    
    # Run every night at 2:00 AM
    scheduler.add_job(
        run_db_optimization,
        trigger=CronTrigger(hour=2, minute=0),
        id="nightly_db_maintenance",
        name="Nightly VACUUM and ANALYZE",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("🚀 Maintenance Worker started. Nightly tasks scheduled at 02:00 AM.")
    return scheduler

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    start_worker()
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
