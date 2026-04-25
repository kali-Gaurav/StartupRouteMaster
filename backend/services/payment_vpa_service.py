"""
Payment VPA Service - Task 1: Merchant Rotation Engine
Handles load balancing between multiple UPI handles and daily volume resets.
"""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import MerchantVPA, AuditLog

logger = logging.getLogger(__name__)

class PaymentVPAService:
    @staticmethod
    def get_next_vpa(db: Session) -> Optional[str]:
        """
        [1.2] Weighted Selection: Pick the active VPA with the lowest current volume.
        [1.4] Health-Aware: Only picks is_active=True.
        [1.8] Limit Enforcement: Returns None if all are over limit.
        """
        # 1. Fetch active merchants sorted by current volume asc
        merchants = db.query(MerchantVPA).filter(
            MerchantVPA.is_active == True,
            MerchantVPA.current_daily_volume < MerchantVPA.daily_limit
        ).order_by(MerchantVPA.current_daily_volume.asc()).all()
        
        if not merchants:
            logger.error("No active Merchant VPAs available or all limits reached.")
            return None
            
        selected = merchants[0]
        return selected.vpa

    @staticmethod
    def increment_volume(db: Session, vpa: str, amount: float):
        """[1.5] Persists usage volume to the merchant."""
        merchant = db.query(MerchantVPA).filter(MerchantVPA.vpa == vpa).first()
        if merchant:
            merchant.current_daily_volume += amount  # type: ignore
            merchant.last_volume_update = datetime.utcnow()  # type: ignore
            db.commit()

    @staticmethod
    def add_transaction(db: Session, booking_id: str, utr: str, amount: float, source_vpa: Optional[str] = None):
        """
        [24.2] Appends a transaction to history.
        [24.6] Checks if total amount met for VERIFIED state.
        """
        from database.models import Booking, EscrowStatus
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking: return False
        
        # 1. Update History
        history = list(booking.transaction_history or [])
        history.append({
            "utr": utr,
            "amount": amount,
            "source_vpa": source_vpa or "",
            "timestamp": datetime.utcnow().isoformat()
        })
        booking.transaction_history = history  # type: ignore
        
        # 2. Sum up total received
        total_received = sum(t["amount"] for t in history)
        required = booking.amount_paid
        
        # 3. State Transition
        if total_received >= required:
            booking.escrow_status = EscrowStatus.VERIFIED
            booking.escrow_message = f"Total received ₹{total_received}. Payment Verified."
        else:
            booking.escrow_message = f"Partial payment received: ₹{total_received}/{required}. Awaiting remaining."
            
        db.commit()
        return True
