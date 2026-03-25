"""
Agent Booking Service - Phase 5 Monetization
Handles manual agent fulfillment requests and state enforcement.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database.models import Booking, EscrowStatus, PassengerDetails, AuditLog
from core.data_structures import Passenger

logger = logging.getLogger(__name__)

class AgentBookingService:
    @staticmethod
    def create_booking_request(
        db: Session, 
        user_id: str, 
        route_id: str, 
        passengers: List[Passenger],
        ticket_fare: float
    ) -> Booking:
        """
        Subtask 42.3 & 42.4: Create a manual agent booking request.
        ENFORCEMENT: Checks if route was unlocked by the user.
        """
        # [42.4] State Machine Enforcement: Must be unlocked
        # For simplicity in this step, we check for a COMPLETED UNLOCK booking for this user/route
        unlock_exists = db.query(Booking).filter(
            Booking.user_id == user_id,
            Booking.route_id == route_id,
            Booking.service_type == "UNLOCK",
            Booking.is_unlocked == True
        ).first()
        
        if not unlock_exists:
            raise ValueError("Route must be unlocked (₹49) before requesting agent booking.")

        # [42.7] & [3.1] Fee Aggregation with strict rounding
        agent_fee = 10.0
        # [3.9] Round to 2 decimals for bank accuracy
        total_amount = round(float(ticket_fare) + agent_fee, 2)
        
        # [27.3] Tatkal Auto-Priority
        from utils.geo_utils import is_tatkal_window
        priority = 0 if is_tatkal_window() else 10
        
        booking = Booking(
            user_id=user_id,
            route_id=route_id,
            amount_paid=total_amount, # This is the LOCKED amount for payment
            service_type="AGENT_BOOKING",
            escrow_status=EscrowStatus.CREATED,
            priority=priority, # [27.3]
            escrow_message="Agent booking requested. Awaiting payment verification.",
            booking_details={
                "ticket_fare": round(float(ticket_fare), 2),
                "agent_fee": round(agent_fee, 2),
                "total_checkout": total_amount,
                "locked_at": datetime.utcnow().isoformat() # [3.5] Price snapshot
            }
        )
        db.add(booking)
        db.flush()
        
        # Add Passengers
        for p in passengers:
            pd = PassengerDetails(
                booking_id=booking.id,
                full_name=p.name,
                age=p.age,
                gender=p.gender
            )
            db.add(pd)
            
        # [42.9] Transactional Integrity
        audit = AuditLog(
            entity_type="Booking",
            entity_id=booking.id,
            action="AGENT_BOOKING_REQUESTED",
            new_value="CREATED",
            performed_by=user_id,
            reason=f"User requested booking for {len(passengers)} passengers."
        )
        db.add(audit)
        
        db.commit()
        db.refresh(booking)
        return booking

    @staticmethod
    def claim_booking(db: Session, booking_id: str, agent_id: str) -> bool:
        """
        Subtask 42.8, 44.2 & 47.2: Agent claims a booking with atomic locking.
        """
        try:
            # [47.2] Atomic SELECT FOR UPDATE to prevent double-claiming
            booking = db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()
            if not booking: return False
            
            # [47.1] Check if already claimed
            if booking.agent_id and booking.agent_id != agent_id:
                logger.warning(f"Booking {booking_id} already claimed by {booking.agent_id}")
                return False
            
            # [44.2] Commission Service: Record ₹10 fee
            from services.commission_service import commission_service
            commission_service.record_commission(db, booking_id, agent_id)
                
            booking.agent_id = agent_id
            booking.escrow_status = EscrowStatus.BOOKING_INITIATED
            booking.escrow_message = f"Agent {agent_id} is processing your booking."
            
            audit = AuditLog(
                entity_type="Booking",
                entity_id=booking.id,
                action="AGENT_CLAIMED",
                old_value="VERIFIED",
                new_value="BOOKING_INITIATED",
                performed_by=agent_id,
                reason="Agent claimed booking for fulfillment (Atomic Lock)."
            )
            db.add(audit)
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Error claiming booking: {e}")
            db.rollback()
            return False
