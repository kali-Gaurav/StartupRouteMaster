import sys
import os
from datetime import datetime, timedelta
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, AuditLog
from services.pnr_verification_service import PNRVerificationService

def verify_task_29():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 29 (LATENCY TRACKER)")
    
    db = SessionLocal()
    booking_id = "B29_LATENCY_TEST"
    
    # 0. Setup
    u = User(id="u29", email="u29@ex.com")
    db.merge(u)
    
    # Simulated claim time (5 mins ago)
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    
    b1 = Booking(
        id=booking_id, user_id="u29", 
        service_type="AGENT_BOOKING", 
        agent_id="AGENT_29",
        escrow_status=EscrowStatus.BOOKING_INITIATED,
        created_at=five_mins_ago,
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    # 1. Complete Booking (Triggers Latency Calc)
    print("  Completing booking to trigger latency calculation...")
    PNRVerificationService.complete_booking(db, booking_id, "PNR292929", "AGENT_29")
    
    # 2. Verify Audit Log Entry
    print("  Checking audit log for latency record...")
    log = db.query(AuditLog).filter(
        AuditLog.entity_id == booking_id,
        AuditLog.action == "BOOKING_COMPLETED"
    ).first()
    
    assert log is not None
    print(f"    Audit Reason: {log.reason}")
    assert "Fulfillment Latency: 5.0 mins" in log.reason
    
    # 3. Cleanup
    db.query(Booking).filter(Booking.id == booking_id).delete()
    db.query(AuditLog).filter(AuditLog.entity_id == booking_id).delete()
    db.commit()
    
    print("\n✅ TASK 29 FULLY VERIFIED: Fulfillment latency is accurately calculated and logged.")

if __name__ == "__main__":
    verify_task_29()
