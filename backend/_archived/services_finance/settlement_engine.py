import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from database.models import Settlement, SettlementExecution, Booking
from services.ledger_service import ledger_service

logger = logging.getLogger("finance.settlement")

class SettlementEngine:
    """
    [Group 2] Idempotent Payout Settlement Engine.
    Handles mass agent payouts and manual financial overrides.
    """
    def __init__(self, db: Session):
        self.db = db

    async def run_daily_settlement(self) -> dict:
        """
        Executes the batch payout pulse for all pending commission settlements.
        """
        execution = SettlementExecution(
            batch_date=datetime.utcnow().date(),
            status="INITIATED"
        )
        self.db.add(execution)
        self.db.commit()

        try:
            pending = self.db.query(Settlement).filter(Settlement.status == "PENDING").all()
            total_amount = 0.0
            
            for s in pending:
                # 🛡️ Safety Pulse: Confirm booking is still final
                booking = self.db.query(Booking).filter(Booking.id == s.booking_id).first()
                if not booking or booking.status == "CANCELLED":
                    logger.warning(f"🚫 [SETTLE] Skipping cancelled/missing booking for settlement {s.id}")
                    continue

                # Finalize Settlement
                s.status = "SETTLED"
                s.settled_at = datetime.utcnow()
                s.execution_id = execution.id
                
                total_amount += s.amount
                
                # Ledger: PLATFORM_REVENUE -> AGENT_BALANCE_SETTLED
                ledger_service.record_transaction(
                    self.db,
                    debit_account="PLATFORM_REVENUE",
                    credit_account="AGENT_BALANCE_SETTLED",
                    amount=s.amount,
                    transaction_type="AGENT_PAYOUT",
                    user_id=s.agent_user_id,
                    metadata={"settlement_id": s.id, "booking_id": s.booking_id}
                )

            execution.total_amount = total_amount
            execution.record_count = len(pending)
            execution.status = "SUCCESS"
            
            self.db.commit()
            logger.info(f"✅ [SETTLE] Batch successful: {len(pending)} records | ₹{total_amount}")
            return {"status": "SUCCESS", "records": len(pending), "amount": total_amount}

        except Exception as e:
            logger.error(f"❌ [SETTLE] Batch Failure: {e}")
            execution.status = "FAILED"
            self.db.commit()
            return {"status": "FAILED", "error": str(e)}

    async def manual_override(self, settlement_id: str, admin_id: str) -> bool:
        """Allows an admin to manually force a settlement (e.g., after a dispute)."""
        s = self.db.query(Settlement).filter(Settlement.id == settlement_id).first()
        if not s: return False
        
        s.status = "SETTLED"
        s.settled_at = datetime.utcnow()
        s.claim_metadata = {"overridden_by": admin_id, "at": datetime.utcnow().isoformat()}
        
        self.db.commit()
        return True

def get_settlement_engine(db: Session):
    return SettlementEngine(db)
