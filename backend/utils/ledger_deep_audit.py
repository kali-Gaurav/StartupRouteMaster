import sqlite3
import logging
import sys
import os

# Set PYTHONPATH
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("nexus-audit")

def verify_ledger_chain():
    logger.info("🧪 Launching NEXUS-AUDIT: Financial Ledger Hash-Chain Verification...")
    
    # We'll use the service's logic directly for deep verification
    from database.session import SessionLocal, initialize_database_pools
    from services.ledger_service import ledger_service
    import asyncio
    
    async def run_audit():
        await initialize_database_pools()
        db = SessionLocal()
        try:
             is_valid = ledger_service.verify_ledger_integrity(db)
             if is_valid:
                  logger.info("✅ SUCCESS: Ledger Hash-Chain Integrity Confirmed.")
                  return 0
             else:
                  logger.error("🛑 AUDIT FAILURE: Ledger Hash-Chain is BROKEN.")
                  return 1
        except Exception as e:
             logger.error(f"🛑 AUDIT FAILURE: {e}")
             return 1
        finally:
             db.close()
             
    return asyncio.run(run_audit())

if __name__ == "__main__":
    sys.exit(verify_ledger_chain())
