import logging
import asyncio
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func
from database.models import FinancialLedger, Booking
from database.session import SessionLocal
from services.agents.base_agent import BaseAgent, AgentPriority

logger = logging.getLogger("nexus.financial.parity")

class FinancialParityAgent(BaseAgent):
    """
    [Group 2] The 'Parity' Ledger Validator Agent.
    An active 'System Builder' that ensures financial ledger vs. state integrity.
    """
    name = "FinancialParityAgent"
    description = "Ledger Validator Agent ensuring financial integrity"
    category = "finance"
    priority = AgentPriority.CRITICAL
    icon = "⚖️"
    color = "#10B981" # Emerald-500
    version = "1.0.0"
    auto_schedule_interval = 60 # Check every 60s

    def __init__(self):
        super().__init__()
        self.check_interval = 60

    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """[G2.2.1] The autonomous heartbeat of financial integrity."""
        db = SessionLocal()
        issues_found = []
        try:
            # 1. Cryptographic Tamper-Chain Verification (Child G2.2.1.3)
            if not await self.verify_tamper_chain(db):
                reason = "CRYPTOGRAPHIC_TAMPER_DETECTED"
                await self.trigger_emergency_lock(reason)
                issues_found.append(reason)
            
            # 2. Bank vs Ledger Parity (Child G2.2.1.1)
            if not await self.verify_bank_ledger_parity(db):
                reason = "FINANCIAL_LEDGER_MISMATCH"
                await self.trigger_emergency_lock(reason)
                issues_found.append(reason)

            # 3. Internal Math Parity
            if not await self.verify_system_parity(db):
                reason = "INTERNAL_MATH_PARITY_FAILURE"
                await self.trigger_emergency_lock(reason)
                issues_found.append(reason)

            # 4. Logical Cross Pillar Audit
            await self.cross_pillar_audit(db)
            
            if issues_found:
                return {
                    "status": "error",
                    "summary": f"Parity failures detected: {', '.join(issues_found)}",
                    "data": {"issues": issues_found}
                }
            return {
                "status": "success",
                "summary": "Financial parity validated successfully",
                "data": {}
            }
            
        except Exception as e:
            logger.error(f"🚨 [PARITY] Execute Error: {e}")
            return {"status": "error", "summary": f"Error: {str(e)}"}
        finally:
            db.close()

    async def pulse(self):
        """Legacy continuous loop. Use execute() instead when registered with swarm."""
        while True:
            await self.execute()
            await asyncio.sleep(self.check_interval)

    async def verify_bank_ledger_parity(self, db) -> bool:
        """
        Compare real-world intake (BankTransactions) with recorded intake (Ledger).
        """
        from database.models import BankTransaction
        
        # Sum of all MATCHED/VOIDED/PROCESSING bank transactions
        bank_sum = db.query(func.sum(BankTransaction.amount)).filter(
            BankTransaction.status != "FAILED"
        ).scalar() or 0.0

        # Sum of all entries in the Ledger that represent bank intake (Source: BANK_LIQUIDITY)
        ledger_sum = db.query(func.sum(FinancialLedger.amount)).filter(
            FinancialLedger.debit_account == "BANK_LIQUIDITY"
        ).scalar() or 0.0

        diff = abs(bank_sum - ledger_sum)
        if diff > 0.01:
            logger.error(f"💣 [PARITY] Bank/Ledger Mismatch! Bank: {bank_sum} | Ledger: {ledger_sum} | Diff: {diff}")
            return False
        return True

    async def verify_tamper_chain(self, db) -> bool:
        """
        Verifies the cryptographic hash chain of the ledger.
        """
        import hashlib
        
        # Check last 50 entries for speed in pulse
        recent_entries = db.query(FinancialLedger).order_by(FinancialLedger.id.desc()).limit(50).all()
        if len(recent_entries) < 2:
            return True

        for i in range(len(recent_entries) - 1):
            current = recent_entries[i]
            previous = recent_entries[i+1] # Descending order means i+1 is 'previous' in timeline
            
            # Reconstruct hash
            data_str = f"{current.transaction_uuid}|{current.amount}|{current.debit_account}|{current.credit_account}|{current.previous_row_hash}"
            expected_hash = hashlib.sha256(data_str.encode()).hexdigest()
            
            if current.cumulative_hash != expected_hash:
                logger.critical(f"🕵️‍♂️ [PARITY] TAMPER DETECTED: Hash mismatch at Ledger ID {current.id}")
                return False
            
            if current.previous_row_hash != previous.cumulative_hash:
                 logger.critical(f"🕵️‍♂️ [PARITY] CHAIN BROKEN: Previous hash mismatch at Ledger ID {current.id}")
                 return False
                 
        return True

    async def verify_system_parity(self, db) -> bool:
        """Placeholder for internal math parity."""
        return True
        
    async def cross_pillar_audit(self, db):
        """Placeholder for logical cross pillar audit."""
        pass

    async def trigger_emergency_lock(self, reason: str):
        """
        Emergency Lock (Child G2.2.1.2).
        Freezes the platform until manual admin intervention.
        """
        from services.cache_service import cache_service
        from services.ws_manager import ws_manager
        
        logger.critical(f"❗❗❗ [EMERGENCY] TRIGGERING PLATFORM LOCK: {reason}")
        
        # 1. Set Redis Safety Latch
        cache_service.set("PLATFORM_FINANCIAL_LOCK", "LOCKED", ttl_seconds=None)
        
        # 2. Broadcast SOS
        await ws_manager.broadcast_global(
            f"🆘 SYSTEM EMERGENCY: Financial Parity Failure ({reason}). Platform is now in READ-ONLY mode.",
            "SOS_ALERT"
        )
        
        # 3. Add to Audit Log
        from database.models import AuditLog
        db = SessionLocal()
        try:
            audit = AuditLog(
                entity_type="SYSTEM",
                entity_id="GLOBAL",
                action="EMERGENCY_LOCK",
                new_value="LOCKED",
                reason=reason
            )
            db.add(audit)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
            db.rollback()
        finally:
            db.close()

# Global Instance
financial_parity_agent = FinancialParityAgent()
