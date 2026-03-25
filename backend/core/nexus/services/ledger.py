import logging
from core.nexus.node import NexusNode
from services.ledger_service import ledger_service
from database.session import SessionLocal

logger = logging.getLogger("nexus.ledger")

class LedgerNode(NexusNode):
    """[Task 5.1] Financial Governance Node for Nexus V3."""
    
    def __init__(self):
        super().__init__("ledger", dependencies=["database"])
        
    async def on_start(self):
        """Perform a startup integrity audit of the hash chain."""
        logger.info("💰 [LEDGER] Running V3 Financial Integrity Audit...")
        
        db = SessionLocal()
        try:
            # Task 49.9: verify the full chain for V3 compliance
            is_valid = ledger_service.verify_ledger_integrity(db)
            if not is_valid:
                raise RuntimeError("Financial Ledger Hash Chain Tamper Detected!")
            logger.info("✅ [LEDGER] Financial Audit Passed. Cryptographic Chain Secured.")
        finally:
            db.close()
            
    async def on_stop(self):
        """Flush any pending audit logs and perform a final check."""
        logger.info("💰 [LEDGER] Closing Financial Governance Node.")
        # Future: If we implement buffered writes, flush them here.
        pass

# Global Singleton
nexus_ledger = LedgerNode()
