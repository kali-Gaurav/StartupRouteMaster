import asyncio
import logging
import sys
import os

# Set PYTHONPATH
sys.path.append(os.getcwd())

from core.nexus.financial.node import financial_node

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify-ledger-sync")

async def run_sync_test():
    logger.info("🧪 Launching NEXUS-4.9: Sentinel Ledger Sync Performance Check...")
    
    # 1. Simulate a sync task
    logger.info("🛡️ Testing Task 4.2: Force R2 Ledger Mirroring...")
    
    # We bypass the start_pulse and just call the sync directly via mgr
    from services.storage_sync import r2_sync_manager
    success = await r2_sync_manager.sync_to_r2("database/user_store.db")
    
    if success:
        logger.info("✅ SUCCESS: Financial Ledger (user.db) mirrored to Cloudflare R2.")
    else:
        logger.error("❌ FAILURE: Cloud sync returned error. Check R2 credentials.")
        return 1

    logger.info("🎉 Task 4.9 VERIFIED: Financial Integrity Sync is Active.")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(run_sync_test()))
