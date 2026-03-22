import os
import sys
import asyncio
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def test_components():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("verify")
    
    logger.info("🔍 Verifying System Components...")
    
    try:
        from core.middleware.engine import SystemStateManager, SmartMiddleware
        from services.storage_sync import r2_sync_manager
        from app import app
        
        logger.info("✅ Imports successful.")
        
        # Test State Manager
        state_manager = SystemStateManager()
        state = state_manager.get_current_state()
        logger.info(f"✅ System State: {state.name}")
        
        # Test R2 Sync Manager paths
        logger.info(f"✅ R2 Sync DB paths: {r2_sync_manager.db_paths}")
        
        # Test Middleware in app
        middleware_names = [type(m.cls).__name__ for m in app.user_middleware]
        logger.info(f"✅ Registered Middlewares: {middleware_names}")
        
        if "SmartMiddleware" in middleware_names:
            logger.info("🚀 SmartMiddleware is correctly registered.")
        else:
            logger.error("❌ SmartMiddleware NOT found in app.user_middleware")
            
        logger.info("✨ Verification complete.")
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_components())
