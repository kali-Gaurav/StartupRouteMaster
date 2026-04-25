
import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from database.session import initialize_database_pools, SessionUser, SessionTransit
from database.models import User, Stop, TrainMaster
from services.rapidapi_provider import rapidapi_provider
from services.multi_layer_cache import multi_layer_cache
from core.container import container

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("nexus_diagnostic")

async def diagnostic():
    logger.info("🚀 Starting Nexus System Diagnostic...")
    
    # 1. Database Diagnostic
    try:
        await initialize_database_pools()
        with SessionUser() as session:
            count = session.query(User).count()
            logger.info(f"✅ User DB: Connected. User count: {count}")
        with SessionTransit() as session:
            count = session.query(Stop).count()
            logger.info(f"✅ Transit DB: Connected. Stop count: {count}")
    except Exception as e:
        logger.error(f"❌ Database Diagnostic FAILED: {e}")

    # 2. Redis / Cache Diagnostic
    try:
        await multi_layer_cache.init()
        if multi_layer_cache.health_latch:
             logger.info("✅ Redis (L2 Cache): HEALTHY")
             test_key = "diagnostic:test"
             await multi_layer_cache.put(test_key, "ALIVE", ttl=10)
             val = await multi_layer_cache.get(test_key)
             if val == "ALIVE":
                 logger.info("✅ Cache Read/Write: VERIFIED")
             else:
                 logger.warning(f"⚠️ Cache Integrity Check: FAILED (Got {val})")
        else:
             logger.warning("⚠️ Redis (L2 Cache): DEGRADED (Only L1/Memory active)")
    except Exception as e:
        logger.error(f"❌ Cache Diagnostic FAILED: {e}")

    # 3. RapidAPI Diagnostic
    try:
        await rapidapi_provider.init()
        if rapidapi_provider.is_healthy:
            logger.info("✅ RapidAPI Provider: INITIALIZED")
            # Try a low-cost call if possible, or just check config
            from database.config import Config
            logger.info(f"🔍 RapidAPI Host: {Config.RAPIDAPI_HOST}")
            if not Config.RAPIDAPI_KEY:
                logger.error("❌ RapidAPI Key: MISSING")
            else:
                logger.info("✅ RapidAPI Key: CONFIGURED")
        else:
            logger.error("❌ RapidAPI Provider: UNHEALTHY")
    except Exception as e:
        logger.error(f"❌ RapidAPI Diagnostic FAILED: {e}")

    logger.info("🏁 Diagnostic Complete.")

if __name__ == "__main__":
    asyncio.run(diagnostic())
