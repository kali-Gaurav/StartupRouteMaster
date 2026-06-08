"""
Cleanup Worker - Task 28: Automated Claim & Lock Release
Background process to ensure system state integrity.
"""

import asyncio
import logging
from database.session import SessionLocal, SessionTransit
from tasks.cleanup_tasks import release_expired_claims
from services.inventory.service import InventoryService

logger = logging.getLogger(__name__)

async def cleanup_loop():
    """
    [28.3] Continuous background loop for releasing expired claims and locks.
    Runs every 60 seconds.
    """
    logger.info("Starting Cleanup Worker Loop...")
    while True:
        try:
            # 1. Release Expired Agent Claims
            db_user = SessionLocal()
            try:
                released_claims = release_expired_claims(db_user)
                if released_claims > 0:
                    logger.info(f"Cleanup: Released {released_claims} expired agent claims.")
            finally:
                db_user.close()
                
            # 2. Release Expired Seat Inventory Locks
            db_transit = SessionTransit()
            try:
                released_locks = InventoryService.release_expired_locks(db_transit)
                if released_locks > 0:
                    logger.info(f"Cleanup: Released {released_locks} expired seat locks.")
            finally:
                db_transit.close()
                
        except Exception as e:
            logger.error(f"Cleanup Loop Error: {e}")
            
        await asyncio.sleep(60) # Run every minute

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(cleanup_loop())
