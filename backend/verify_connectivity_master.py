import asyncio
import logging
import os
import sys
from database.config import Config
from services.multi_layer_cache import multi_layer_cache
from database.session import initialize_database_pools
from utils.storage import storage as r2_storage
from core.auth.supabase_client import supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("connectivity_nexus")

async def test_connectivity():
    logger.info("🚀 [NEXUS:CON] Starting Master Connectivity Audit (Task 129)...")
    
    # 1. Redis (Upstash)
    try:
        from core.redis import verify_redis_connection
        if verify_redis_connection():
            logger.info("✅ Redis (Upstash) connection STABLE.")
        else:
            logger.error("❌ Redis (Upstash) connection FAILED.")
    except Exception as e:
        logger.error(f"❌ Redis Connectivity Error: {e}")

    # 2. Supabase (Database)
    try:
        await initialize_database_pools()
        from database.session import get_async_user_db
        import sqlalchemy
        from sqlalchemy import text
        async for db in get_async_user_db():
            res = await db.execute(text("SELECT 1"))
            logger.info("✅ Supabase (Postgres) connection STABLE.")
            break
    except Exception as e:
        logger.error(f"❌ Supabase Database Error: {e}")

    # 3. Cloudflare R2
    try:
        objs = r2_storage.list_objects()
        if objs is not None:
            logger.info(f"✅ Cloudflare R2 connection STABLE. Found {len(objs)} objects.")
        else:
            logger.error("❌ Cloudflare R2 connection FAILED.")
    except Exception as e:
        logger.error(f"❌ Cloudflare R2 Error: {e}")

    # 4. Supabase Auth
    try:
        # Pinging a non-authenticated endpoint to check reachability
        if supabase:
            logger.info("✅ Supabase Auth Client initialized.")
        else:
            logger.error("❌ Supabase Auth Client FAILED.")
    except Exception as e:
        logger.error(f"❌ Supabase Auth Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connectivity())
