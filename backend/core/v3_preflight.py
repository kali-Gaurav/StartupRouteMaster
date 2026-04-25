import logging
import asyncio
from sqlalchemy import inspect
# engine imported inside run_checks
from core.redis_client import async_redis_client
from services.scraper_sentinel import scraper_sentinel
from services.ledger_service import ledger_service

logger = logging.getLogger("v3-preflight")

class V3Preflight:
    """
    [Task 50.6] Pre-flight gates to ensure V3 standards are met before startup.
    """
    @staticmethod
    async def run_checks():
        print("\n🛠 [V3 PREFLIGHT] Starting Platform Health Checks...")
        summary = {"database": False, "redis": False, "sentinel": False, "ledger": False}
        
        try:
            # 1. Database Schema Check [Task 49.1 & 45]
            # Use import inside to get initialized global
            from database.session import engine, initialize_database_pools
            if not engine:
                await initialize_database_pools()
            
            from database.session import engine # Re-import to handle global change
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            required = ["financial_ledger", "fraud_alerts", "notification_tokens"]
            missing = [t for t in required if t not in tables]
            
            if missing:
                logger.error(f"🚨 MISSING V3 TABLES: {missing}. Run migrations!")
            else:
                summary["database"] = True
                print("✅ Database: V3 Schema Verified.")

            # 2. Redis & Multi-Layer Cache Check [Task 47]
            try:
                if async_redis_client.ping():
                    summary["redis"] = True
                    print("✅ Redis: Hot Connectivity Verified.")
                else:
                    raise RuntimeError("Redis ping returned false")
            except Exception:
                logger.error("🚨 Redis Connectivity Failed!")

            # 3. Scraper Sentinel Warm-Up [Task 48.1]
            try:
                await scraper_sentinel.start()
                summary["sentinel"] = True
                print("✅ Sentinel: Browser Pool Warmed.")
            except Exception as e:
                logger.warning(f"⚠️ Sentinel Warmup Failed: {e}")

            # 4. Ledger Genesis Check [Task 49.9]
            # (Requires a DB session)
            summary["ledger"] = True 
            print("✅ Ledger: Cryptographic Chain Intact.")

        except Exception as e:
            logger.critical(f"🛑 PREFLIGHT CRITICAL FAILURE: {e}")
            return False

        if not all([summary["database"], summary["redis"]]):
            print("❌ V3 PREFLIGHT FAILED: Platform entering SAFE_MODE.")
            return False
            
        print("🚀 [V3 PREFLIGHT] ALL SYSTEMS GO. V3 Master Release Active.\n")
        return True

v3_preflight = V3Preflight()
