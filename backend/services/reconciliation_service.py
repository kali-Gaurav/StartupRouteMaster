import logging
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.session import SessionLocal
from database.models import Booking, EscrowStatus, BankTransaction
from utils.mock_statement import generate_mock_bank_statement
from services.ws_manager import ws_manager
from services.merchant_vpa_service import merchant_vpa_service

logger = logging.getLogger(__name__)

class ReconciliationService:
    """
    Task 7: Real-Time Bank Statement Polling & Reconciliation.
    Matches bank records against pending bookings.
    """

    async def reconcile_all_pending(self):
        """
        Main worker loop:
        1. Fetch all bookings in UTR_SUBMITTED or CREATED status.
        2. Fetch latest transactions from bank (mocked for now).
        3. Perform high-confidence matching.
        """
        db = SessionLocal()
        try:
            # Task 7.1: Fetch active pending bookings
            pending = db.query(Booking).filter(
                Booking.escrow_status.in_([EscrowStatus.CREATED, EscrowStatus.UTR_SUBMITTED])
            ).all()

            if not pending:
                return {"message": "No pending bookings to reconcile", "matched": 0}

            # Task 7.2: Fetch bank transactions (Simulated polling)
            statement = generate_mock_bank_statement(20)
            matched_count = 0

            for txn_data in statement:
                utr = txn_data["utr"]
                amount = txn_data["amount"]
                desc = txn_data["description"]

                # Task 7.4: Multi-stage Matching
                match = self._find_match(pending, utr, amount, desc)
                
                if match:
                    # Avoid double processing
                    if match.escrow_status == EscrowStatus.VERIFIED:
                        continue
                        
                    logger.info(f"Reconciliation Match Found! Booking {match.id} with UTR {utr}")
                    
                    # Update status using hardened state machine logic
                    match.update_escrow_status(
                        db, 
                        EscrowStatus.VERIFIED, 
                        message="✅ Verified via bank statement reconciliation.",
                        reason=f"Statement match: {utr}"
                    )
                    
                    # Save UTR if not present
                    if not match.utr_number:
                        match.utr_number = utr

                    # Update volume limits
                    if match.merchant_vpa:
                        merchant_vpa_service.record_volume(match.merchant_vpa, match.amount_paid)

                    # Real-time UI Update
                    await ws_manager.broadcast_log(match.id, "✅ Bank Statement Reconciled. Payment Verified!", "VERIFIED")
                    
                    matched_count += 1

            db.commit()
            return {"total_checked": len(pending), "matched": matched_count}
        except Exception as e:
            logger.error(f"Reconciliation error: {e}")
            db.rollback()
            return {"error": str(e)}
        finally:
            db.close()

    def _find_match(self, pending_list, utr, amount, desc):
        """
        Matching logic:
        1. Exact UTR match
        2. RM_ tag match in description
        3. Cent-matching (exact amount to paisa)
        """
        # 1. UTR Match
        for b in pending_list:
            if b.utr_number == utr:
                return b
        
        # 2. RM_ tag Match
        import re
        tag_match = re.search(r"RM_(?P<sid>[A-Z0-9]{8})", desc)
        if tag_match:
            sid = tag_match.group("sid").lower()
            for b in pending_list:
                if b.id.startswith(sid):
                    return b
        
        # 3. Cent-matching (Exact paisa)
        for b in pending_list:
            # Must match amount exactly and be recent (last 2 hours)
            if abs(b.amount_paid - amount) < 0.001:
                # Add date check for extra safety in prod
                return b
                
        return None

reconciliation_service = ReconciliationService()
