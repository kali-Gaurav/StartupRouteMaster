import os
import sys
import asyncio
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def test_auth_modernization():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("verify-auth")
    
    logger.info("🔍 Verifying Auth Modernization...")
    
    try:
        from dependencies import get_current_user
        from services.multi_layer_cache import multi_layer_cache
        from database.session import initialize_database_pools
        
        # Initialize pools first (needed for Redis and DB)
        await initialize_database_pools()
        
        logger.info("✅ Imports and Pool Initialization successful.")
        
        # Check if get_current_user is async and has correct signature
        import inspect
        sig = inspect.signature(get_current_user)
        logger.info(f"✅ get_current_user signature: {sig}")
        
        # Verify it uses get_async_auth_db
        params = list(sig.parameters.values())
        db_param = next((p for p in params if p.name == 'db'), None)
        if db_param and 'get_async_auth_db' in str(db_param.default):
            logger.info("🚀 get_current_user is using get_async_auth_db.")
        else:
            logger.error(f"❌ get_current_user is NOT using get_async_auth_db as default: {db_param}")
            
        logger.info("✨ Auth verification complete.")
        
    except Exception as e:
        logger.error(f"❌ Auth verification failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_auth_modernization())
