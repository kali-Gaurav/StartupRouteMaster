import logging
from sqlalchemy import func
from database.session import SessionLocal
from database.models import Booking, CommissionTracking, User, EscrowStatus

logger = logging.getLogger("commission-audit")

def audit_commission_health():
    """
    [Task 44.10] Daily Leakage Audit.
    Ensures Booking Count * ₹10 == Commission Count.
    """
    db = SessionLocal()
    try:
        # 1. Count Completed Agent Bookings
        completed_bookings = db.query(Booking).filter(
            Booking.service_type == "AGENT_BOOKING",
            # Assuming COMPLETED is the final state for payout
            # In our current logic, COMPLETED means the PNR was submitted successfully.
            Booking.escrow_status == EscrowStatus.COMPLETED 
        ).all()
        
        booking_ids = [b.id for b in completed_bookings]
        
        # 2. Count Commission Records
        comm_bookings = db.query(CommissionTracking.booking_id).all()
        comm_ids = {c.booking_id for c in comm_bookings}
        
        # 3. Find Mismatches
        leaked_bookings = [bid for bid in booking_ids if bid not in comm_ids]
        
        if leaked_bookings:
            logger.error(f"⚠️ COMMISSION LEAKAGE DETECTED: {len(leaked_bookings)} bookings missing commission records.")
            # SUGGESTION: Auto-Patching
            for bid in leaked_bookings:
                booking = db.query(Booking).filter(Booking.id == bid).first()
                if booking and booking.agent_id:
                   from services.commission_service import commission_service
                   agent_id = str(booking.agent_id)  # type: ignore
                   logger.warning(f"🛠 Auto-Patching commission for booking {bid}")
                   commission_service.record_commission(db, bid, agent_id)
        else:
            logger.info("✅ Commission Integrity Audit: Healthy (Zero Leakage).")
            
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    audit_commission_health()
