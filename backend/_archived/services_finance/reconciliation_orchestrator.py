import logging
import asyncio
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models import Booking, UnclaimedFund, FinancialLedger, EscrowStatus
from services.ledger_service import ledger_service
from services.ws_manager import ws_manager

logger = logging.getLogger("finance.reconciliation")

class ReconciliationOrchestrator:
    """
    [Group 2] Unified Financial Reconciliation Orchestrator.
    Processes bank events and manages the 'Limbo' unclaimed funds queue.
    Ensures zero-loss commission tracking and systemic transparency.
    """
    def __init__(self, db: Session):
        self.db = db

    async def process_bank_event(self, utr: str, amount: float, sender_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempts to match a bank credit event to an active booking.
        """
        logger.info(f"💰 [RECON] Processing Bank Event: UTR {utr} | Amount {amount}")

        # 1. Primary Match: UTR + Amount
        booking = self.db.query(Booking).filter(
            Booking.utr_number == utr
        ).first()

        if booking:
            # 2. Verify Amount Integrity
            if abs(booking.amount_paid - amount) < 0.01:
                logger.info(f"✅ [RECON] Exact match found for Booking {booking.id}")
                return await self._handle_successful_match(booking, utr, sender_info)
            else:
                logger.warning(f"⚠️ [RECON] UTR Match but AMOUNT MISMATCH! Expected {booking.amount_paid}, Got {amount}")
                return await self._move_to_limbo(utr, amount, sender_info, f"Amount Mismatch (Expected {booking.amount_paid})")

        # 3. No Match Found -> Move to 'Limbo'
        logger.info(f"👻 [RECON] No booking match for UTR {utr}. Moving to Unclaimed Funds.")
        return await self._move_to_limbo(utr, amount, sender_info, "No Matching Booking")

    async def _handle_successful_match(self, booking: Booking, utr: str, sender_info: Dict[str, Any]) -> Dict[str, Any]:
        """Finalizes a matched booking and records it in the ledger."""
        try:
            # Update Booking Status
            if booking.escrow_status == EscrowStatus.UTR_SUBMITTED:
                booking.update_escrow_status(
                    self.db, 
                    EscrowStatus.VERIFIED, 
                    message="✅ Payment verified via Automated Reconciliation Nerve Center.",
                    performed_by="SYSTEM_RECON",
                    reason=f"Auto-match UTR {utr}"
                )
            
            # Record Platform Commission in Ledger
            # logic: USER_PAYMENT -> PLATFORM_ESCROW
            ledger_service.record_transaction(
                self.db,
                debit_account="CASH_ESCROW",
                credit_account="PLATFORM_REVENUE",
                amount=booking.amount_paid,
                transaction_type="BOOKING_RECON",
                user_id=booking.user_id,
                metadata={"utr": utr, "booking_id": booking.id}
            )
            
            self.db.commit()
            
            # Notify WebSocket for real-time dashboard update
            await ws_manager.broadcast_log(booking.id, "✅ Payment successfully reconciled and moved to verified escrow.", "VERIFIED")
            
            return {"status": "MATCHED", "booking_id": booking.id}
        except Exception as e:
            logger.error(f"Recon Match Error: {e}")
            self.db.rollback()
            return {"status": "ERROR", "message": str(e)}

    async def _move_to_limbo(self, utr: str, amount: float, sender_info: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """Saves an orphan transaction for manual admin reconciliation."""
        try:
            # Check if already exists in limbo
            existing = self.db.query(UnclaimedFund).filter(UnclaimedFund.utr_number == utr).first()
            if existing:
                return {"status": "ALREADY_IN_LIMBO", "id": existing.id}

            limbo_entry = UnclaimedFund(
                utr_number=utr,
                amount=amount,
                sender_info=sender_info,
                claim_metadata={"reason": reason}
            )
            self.db.add(limbo_entry)
            
            # Audit in Ledger as 'PENDING_UNIDENTIFIED'
            ledger_service.record_transaction(
                self.db,
                debit_account="CASH_ESCROW",
                credit_account="UNCLAIMED_SUSPENSE",
                amount=amount,
                transaction_type="UNCLAIMED_ENTRY",
                metadata={"utr": utr, "reason": reason}
            )
            
            self.db.commit()
            logger.warning(f"🚨 [RECON] Unclaimed fund recorded: UTR {utr}")
            return {"status": "LIMBO", "id": limbo_entry.id, "reason": reason}
        except Exception as e:
            logger.error(f"Limbo Entry Error: {e}")
            self.db.rollback()
            return {"status": "ERROR", "message": str(e)}

# Factory
def get_reconciliation_orchestrator(db: Session):
    return ReconciliationOrchestrator(db)
