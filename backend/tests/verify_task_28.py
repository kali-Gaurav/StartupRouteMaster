import sys
import os
from datetime import datetime, timedelta
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus
from tasks.cleanup_tasks import release_expired_claims

def verify_task_28():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 28 (AUTO CLAIM RELEASE)")
    
    db = SessionLocal()
    booking_id = "B28_EXPIRY_TEST"
    
    # 0. Setup test data
    u = User(id="u28", email="u28@ex.com")
    db.merge(u)
    
    # Simulate a claim made 20 mins ago
    twenty_mins_ago = datetime.utcnow() - timedelta(minutes=20)
    
    b1 = Booking(
        id=booking_id, user_id="u28", 
        service_type="AGENT_BOOKING",
        escrow_status=EscrowStatus.BOOKING_INITIATED, 
        agent_id="AGENT_SLOW",
        created_at=twenty_mins_ago,
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    print(f"  Setup: Booking {booking_id} claimed 20 mins ago.")
    
    # 1. Run Cleanup
    print("  Running release_expired_claims utility...")
    released = release_expired_claims(db)
    print(f"    Released count: {released}")
    
    # 2. Verify State
    b1 = db.query(Booking).filter(Booking.id == booking_id).first()
    print(f"    Final Status: {b1.escrow_status.value}")
    print(f"    Agent ID: {b1.agent_id}")
    
    assert released >= 1
    assert b1.escrow_status == EscrowStatus.VERIFIED
    assert b1.agent_id == None
    
    # 3. Cleanup
    db.delete(b1)
    db.commit()
    
    print("\n✅ TASK 28 FULLY VERIFIED: Expired claims are automatically released to the queue.")

if __name__ == "__main__":
    verify_task_28()
