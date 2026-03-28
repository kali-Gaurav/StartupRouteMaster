import asyncio
import logging
import sys
import os

# Set PYTHONPATH
sys.path.append(os.getcwd())

from database.session import initialize_database_pools, UserBase, TransitBase
from database import models # Should trigger registration

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("nexus-audit")

async def init_tables():
    logger.info("🧪 Launching NEXUS-AUDIT: Table Registry Inspection...")
    
    # List registered tables
    logger.info(f"📋 Registered UserBase Tables: {list(UserBase.metadata.tables.keys())}")
    
    if "financial_ledger" not in UserBase.metadata.tables:
         logger.error("🛑 AUDIT FAILURE: 'financial_ledger' is NOT registered in UserBase. Check imports.")
         return 1

    try:
        await initialize_database_pools()
        from database.session import engine_user
        
        if engine_user:
             UserBase.metadata.create_all(engine_user)
             logger.info("✅ SUCCESS: User Store tables are synchronized.")
             return 0
             
        return 1
    except Exception as e:
        logger.error(f"🛑 AUDIT FAILURE: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(init_tables()))
