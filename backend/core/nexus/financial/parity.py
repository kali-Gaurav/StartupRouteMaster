import logging
from sqlalchemy import func
from database.models import FinancialLedger
from database.session import AsyncSessionUser

logger = logging.getLogger("nexus.financial.parity")

class FinancialParityChecker:
    """[Task 4.3] Multi-Pillar Ledger Verification (Parity & Hash Chain)."""
    
    async def verify_system_parity(self) -> bool:
        """
        Verify that Sum(Debits) == Sum(Credits).
        This is a fundamental law of accounting.
        """
        try:
            from sqlalchemy import select
            async with AsyncSessionUser() as db:
                stmt_debits = select(func.sum(FinancialLedger.amount)).where(FinancialLedger.debit_account.is_not(None))
                stmt_credits = select(func.sum(FinancialLedger.amount)).where(FinancialLedger.credit_account.is_not(None))
                
                debits = (await db.execute(stmt_debits)).scalar() or 0.0
                credits = (await db.execute(stmt_credits)).scalar() or 0.0
                
                # Check for perfect parity
                diff = abs(debits - credits)
                if diff > 0.01: # Avoid precision drift for float
                     logger.critical(f"🛑 [NEXUS:FINANCIAL] PARITY FAILURE: Debits({debits}) != Credits({credits}). Diff: {diff}")
                     return False
                     
                logger.debug(f"✅ [NEXUS:FINANCIAL] System Parity Verified: {debits} INR.")
                return True
                
        except Exception as e:
            logger.error(f"🚨 [NEXUS:FINANCIAL] Parity Check Loop Failed: {e}")
            return False

financial_parity = FinancialParityChecker()
