import asyncio
import logging
from sqlalchemy import text
from database.session import initialize_database_pools, async_engine_transit, _pools_initialized

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transit-patch")

async def patch_transit():
    from database import session
    await session.initialize_database_pools()
    
    if not session.async_engine_transit:
        logger.error("Transit engine failed to initialize.")
        return

    async with session.async_engine_transit.begin() as conn:
        logger.info("Patching TRANSIT_DB [station_realtime_heartbeats]...")
        
        # SQLite doesn't support ADD COLUMN IF NOT EXISTS easily in SQL, 
        # so we try-except each.
        cols = [
            ("station_mode", "VARCHAR(20) DEFAULT 'RAIL'"),
            ("connectivity_score", "FLOAT DEFAULT 1.0"),
            ("sync_hash", "VARCHAR(64)")
        ]
        
        for col_name, col_def in cols:
            try:
                await conn.execute(text(f"ALTER TABLE station_realtime_heartbeats ADD COLUMN {col_name} {col_def}"))
                logger.info(f"Added column: {col_name}")
            except Exception as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    logger.info(f"Column {col_name} already exists.")
                else:
                    logger.warning(f"Failed to add {col_name}: {e}")
                    
    logger.info("Transit DB Hardening Complete.")

if __name__ == "__main__":
    asyncio.run(patch_transit())
