import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.agent_booking_service import AgentBookingService
from database.session import SessionLocal
from database.models import User, Booking, CommissionTracking, EscrowStatus

def verify_task_44():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 44 (AGENT FEE TRACKER)")
    
    db = SessionLocal()
    agent_id = "test-agent-44"
    booking_id = "test-booking-44"
    
    # 0. Setup Agent, User and Booking
    agent = User(id=agent_id, email="agent44@example.com", full_name="Test Agent 44", role="agent")
    db.merge(agent)
    
    test_user = User(id="some-user", email="user44@example.com", full_name="Test User 44")
    db.merge(test_user)
    
    booking = Booking(
        id=booking_id, user_id="some-user", route_id="some-route",
        service_type="AGENT_BOOKING", escrow_status=EscrowStatus.VERIFIED,
        amount_paid=1010.0, booking_details={}
    )
    db.merge(booking)
    db.commit()
    
    # 1. Claim Booking
    print("  Claiming booking as agent...")
    success = AgentBookingService.claim_booking(db, booking_id, agent_id)
    assert success == True
    
    # 2. Verify Commission
    print("  Verifying commission record...")
    comm = db.query(CommissionTracking).filter(CommissionTracking.booking_id == booking_id).first()
    
    print(f"    Commission ID: {comm.id}")
    print(f"    Agent ID: {comm.user_id}")
    print(f"    Amount: ₹{comm.amount}")
    
    assert comm is not None
    assert comm.user_id == agent_id
    assert comm.amount == 10.0
    
    # 3. Test Earnings Aggregate (Subtask 44.4)
    from sqlalchemy import func
    total_earnings = db.query(func.sum(CommissionTracking.amount)).filter(CommissionTracking.user_id == agent_id).scalar()
    print(f"    Total Agent Earnings: ₹{total_earnings}")
    assert total_earnings >= 10.0
    
    # 4. Cleanup
    db.query(CommissionTracking).filter(CommissionTracking.booking_id == booking_id).delete()
    db.query(Booking).filter(Booking.id == booking_id).delete()
    db.query(User).filter(User.id.in_([agent_id, "some-user"])).delete()
    db.commit()
    
    print("\n✅ TASK 44 FULLY VERIFIED: Commission tracking is accurate.")

if __name__ == "__main__":
    verify_task_44()
