"""
PNR Verification Service - Phase 5 Fulfillment
Handles the finalization of bookings by agents.
"""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database.models import Booking, EscrowStatus, BookingAuditLog

logger = logging.getLogger(__name__)

class PNRVerificationService:
    @staticmethod
    def complete_booking(
        db: Session, 
        booking_id: str, 
        pnr_number: str, 
        agent_id: str,
        ticket_pdf_url: Optional[str] = None
    ) -> bool:
        """
        Subtask 48.2 & 48.5: Mark a booking as COMPLETED with PNR.
        """
        # 1. Find the booking
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            logger.error(f"Booking {booking_id} not found.")
            return False
            
        # 2. Security Check (Subtask 48.9)
        if booking.agent_id != agent_id:
            logger.warning(f"Unauthorized PNR entry by {agent_id} for booking {booking_id}")
            return False
            
        # 3. PNR Uniqueness (Subtask 48.3)
        existing_pnr = db.query(Booking).filter(
            Booking.pnr_number == pnr_number,
            Booking.id != booking_id
        ).first()
        if existing_pnr:
            raise ValueError(f"PNR {pnr_number} is already linked to another booking.")

        # 4. Update and Transition
        old_status = booking.escrow_status.value
        booking.pnr_number = pnr_number
        booking.ticket_pdf_url = ticket_pdf_url or f"https://cdn.routemaster.io/tickets/{pnr_number}.pdf"
        booking.escrow_status = EscrowStatus.COMPLETED
        booking.escrow_message = "Booking confirmed. PNR verified."
        
        # [29.2] Latency Tracking
        fulfillment_latency = 0
        if booking.created_at:
            fulfillment_latency = (datetime.utcnow() - booking.created_at).total_seconds() / 60
            
        # 5. Audit Log (Subtask 48.7)
        audit = BookingAuditLog(
            booking_id=booking.id,
            action="COMPLETED",
            actor_type="USER",
            actor_id=agent_id,
            reason=f"PNR {pnr_number} verified. Fulfillment Latency: {fulfillment_latency:.1f} mins.",
            extra_data={"old_value": old_status, "new_value": "COMPLETED"}
        )
        db.add(audit)
        
        db.commit()
        logger.info(f"Booking {booking_id} completed with PNR {pnr_number}")
        return True
