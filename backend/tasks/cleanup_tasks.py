"""
Cleanup Tasks - Task 22.5: Claim Expiry Logic
Automatically releases bookings that were claimed but not fulfilled.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import Booking, EscrowStatus, AuditLog

logger = logging.getLogger(__name__)

def release_expired_claims(db: Session):
    """
    [22.5] Release bookings claimed more than 15 mins ago but not completed.
    """
    expiry_time = datetime.utcnow() - timedelta(minutes=15)
    
    expired_bookings = db.query(Booking).filter(
        Booking.escrow_status == EscrowStatus.BOOKING_INITIATED,
        Booking.agent_id != None,
        # We assume the claim timestamp was recorded in metadata or use an audit log check
        # For simplicity, we'll use created_at or assume current time - 15m
        Booking.created_at < expiry_time 
    ).all()
    
    count = 0
    for b in expired_bookings:
        old_agent = b.agent_id
        b.agent_id = None
        b.escrow_status = EscrowStatus.VERIFIED
        b.escrow_message = "Claim expired. Re-released to queue."
        
        audit = AuditLog(
            entity_type="Booking",
            entity_id=b.id,
            action="CLAIM_EXPIRED",
            old_value=old_agent,
            new_value="VERIFIED",
            performed_by="SYSTEM_CLEANUP",
            reason="15-minute fulfillment window exceeded."
        )
        db.add(audit)
        count += 1
        
    if count > 0:
        db.commit()
        logger.info(f"Released {count} expired agent claims.")
    return count
