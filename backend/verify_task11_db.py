import os
import sys
import asyncio
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def test_db_manager():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("verify-db-mgr")
    
    logger.info("🔍 Verifying Task 11: DB Connection Manager...")
    
    try:
        from database.session import initialize_database_pools, get_async_db
        from database.manager import db_manager
        
        # 1. Initialize Pools
        await initialize_database_pools()
        
        # 2. Run a query and check profiling
        from sqlalchemy import text
        async for session in get_async_db():
            logger.info("Running test query (SELECT 1)...")
            await session.execute(text("SELECT 1"))
            await session.commit()
            
        # 3. Check stats
        from database.session import async_engine_user
        stats = db_manager.get_pool_stats(async_engine_user.sync_engine)
        logger.info(f"✅ Pool Stats: {stats}")
        
        if stats['total_queries'] > 0:
            logger.info("✅ Query Profiling is WORKING.")
        else:
            logger.error("❌ Query Profiling NOT CAPTURED.")

        logger.info("✨ Task 11 Verification Complete.")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"❌ Verification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_db_manager())
