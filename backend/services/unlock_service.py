"""
Unlock Service - Phase 5 Monetization
Handles the logic for locking/unlocking journey details and masking sensitive data.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database.models import Booking, EscrowStatus, UnlockedRoute
from core.data_structures import Route, RouteSegment

logger = logging.getLogger(__name__)

class UnlockService:
    @staticmethod
    def mask_route(route_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Subtask 41.5: Mask sensitive train details for locked routes.
        Hides Train Number, Train Name, and Platforms.
        """
        masked = route_dict.copy()
        masked["is_locked"] = True
        
        # Mask Segments
        for seg in masked.get("segments", []):
            seg["train_number"] = "XXXXX"
            seg["train_name"] = "Hidden Train"
            seg["departure_platform"] = "X"
            seg["arrival_platform"] = "X"
            if "trip_id" in seg: seg["trip_id"] = "hidden"
            
        # Also mask 'legs' if present
        for leg in masked.get("legs", []):
            leg["train_number"] = "XXXXX"
            leg["train_name"] = "Hidden Train"
            leg["departure_platform"] = "X"
            leg["arrival_platform"] = "X"

        return masked

    @staticmethod
    def create_unlock_request(db: Session, user_id: str, route_id: str, amount: float = 49.0) -> Booking:
        """
        Subtask 41.3 & 41.4: Initiate an unlock request.
        """
        unlock_booking = Booking(
            user_id=user_id,
            route_id=route_id,
            amount_paid=amount,
            service_type="UNLOCK",
            escrow_status=EscrowStatus.CREATED,
            escrow_message="Payment pending for route unlock.",
            is_unlocked=False,
            booking_details={} # Satisfy NOT NULL
        )
        db.add(unlock_booking)
        db.flush() # Get ID
        
        # [41.4] Payment Integration: Create a PaymentSession record
        from database.models import PaymentSession
        import secrets
        pay_session = PaymentSession(
            user_id=user_id,
            route_id=route_id,
            amount=amount,
            session_code=f"UNL-{secrets.token_hex(4).upper()}",
            status="PENDING"
        )
        db.add(pay_session)
        
        # [41.9] Audit Log
        from database.models import AuditLog
        audit = AuditLog(
            entity_type="Booking",
            entity_id=unlock_booking.id,
            action="UNLOCK_INITIATED",
            new_value="CREATED",
            performed_by=user_id,
            reason="User initiated ₹49 unlock flow."
        )
        db.add(audit)
        
        db.commit()
        db.refresh(unlock_booking)
        return unlock_booking

    @staticmethod
    def fulfill_unlock(db: Session, booking_id: str) -> bool:
        """
        Subtask 41.7: Set route as unlocked upon payment verification.
        """
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking: return False
        
        booking.is_unlocked = True
        booking.escrow_status = EscrowStatus.COMPLETED
        booking.escrow_message = "Route successfully unlocked."
        
        # Record in UnlockedRoute for persistent access
        from database.models import UnlockedRoute
        unlocked = UnlockedRoute(
            user_id=booking.user_id,
            # Link to booking
        )
        db.add(unlocked)
        
        # [41.9] Audit Log
        from database.models import AuditLog
        audit = AuditLog(
            entity_type="Booking",
            entity_id=booking.id,
            action="UNLOCK_COMPLETED",
            old_value="CREATED",
            new_value="COMPLETED",
            performed_by="SYSTEM_PAYMENT",
            reason="Payment verified. Details revealed."
        )
        db.add(audit)
        
        db.commit()
        return True
