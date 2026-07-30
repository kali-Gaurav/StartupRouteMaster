import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, AuditLog, CommissionTracking
from services.agent_booking_service import AgentBookingService

def verify_task_47():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 47 (MANUAL CLAIM LOCK)")
    
    db = SessionLocal()
    booking_id = "test-claim-lock-47"
    
    # 0. Setup Agents, User and Booking
    a1 = User(id="AGENT_1", email="a1@ex.com", role="agent")
    a2 = User(id="AGENT_2", email="a2@ex.com", role="agent")
    u1 = User(id="some-user", email="u1@ex.com", role="user")
    db.merge(a1)
    db.merge(a2)
    db.merge(u1)
    
    booking = Booking(
        id=booking_id, user_id="some-user", route_id="some-route",
        service_type="AGENT_BOOKING", escrow_status=EscrowStatus.VERIFIED,
        amount_paid=500.0, booking_details={}
    )
    db.merge(booking)
    db.commit()
    
    # 1. First Claim (Agent 1)
    print("  Agent 1 claiming booking...")
    res1 = AgentBookingService.claim_booking(db, booking_id, "AGENT_1")
    print(f"    Agent 1 Result: {res1}")
    assert res1 == True
    
    # 2. Second Claim (Agent 2) - Should Fail
    print("  Agent 2 attempting to claim same booking...")
    res2 = AgentBookingService.claim_booking(db, booking_id, "AGENT_2")
    print(f"    Agent 2 Result: {res2} (Expected: False)")
    assert res2 == False
    
    # 3. Verify Database State
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    print(f"    Final Agent ID in DB: {booking.agent_id}")
    assert booking.agent_id == "AGENT_1"
    
    # 4. Cleanup
    db.query(CommissionTracking).filter(CommissionTracking.booking_id == booking_id).delete()
    db.query(Booking).filter(Booking.id == booking_id).delete()
    db.query(User).filter(User.id.in_(["AGENT_1", "AGENT_2"])).delete()
    db.commit()
    
    print("\n✅ TASK 47 FULLY VERIFIED: Manual claim locking prevents double-allocation.")

if __name__ == "__main__":
    verify_task_47()
