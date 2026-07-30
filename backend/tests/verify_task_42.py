import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.agent_booking_service import AgentBookingService
from services.unlock_service import UnlockService
from database.session import SessionLocal
from database.models import User, Booking, PassengerDetails, AuditLog
from core.data_utils.structures import Passenger

def verify_task_42():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 42 (AGENT BOOKING LOGIC)")
    
    db = SessionLocal()
    user_id = "test-user-42"
    route_id_unlocked = "T12625_UNLOCKED"
    route_id_locked = "T99999_LOCKED"
    
    # 0. Setup User
    test_user = User(id=user_id, email="test42@example.com", full_name="Test User 42")
    db.merge(test_user)
    
    # 1. Setup Unlocked Route (Fake previous COMPLETED booking)
    unlock_record = Booking(
        user_id=user_id, route_id=route_id_unlocked, 
        service_type="UNLOCK", is_unlocked=True, 
        escrow_status="COMPLETED", booking_details={}
    )
    db.add(unlock_record)
    db.commit()
    
    # 2. Test Success Flow (Unlocked Route)
    print("  Testing Booking Request for Unlocked Route...")
    passengers = [
        Passenger(name="John Doe", age=35, gender="M"),
        Passenger(name="Jane Doe", age=32, gender="F")
    ]
    ticket_fare = 1500.0
    
    booking = AgentBookingService.create_booking_request(
        db, user_id, route_id_unlocked, passengers, ticket_fare
    )
    
    print(f"    Booking ID: {booking.id}")
    print(f"    Total Amount: ₹{booking.amount_paid} (Expected: ₹1510.0)")
    assert booking.amount_paid == 1510.0
    assert booking.service_type == "AGENT_BOOKING"
    
    # Verify Passengers
    pd_count = db.query(PassengerDetails).filter(PassengerDetails.booking_id == booking.id).count()
    print(f"    Passenger Count: {pd_count}")
    assert pd_count == 2
    
    # 3. Test Failure Flow (Locked Route)
    print("\n  Testing Enforcement: Booking for Locked Route...")
    try:
        AgentBookingService.create_booking_request(
            db, user_id, route_id_locked, passengers, ticket_fare
        )
        print("    ❌ FAILURE: Allowed booking for locked route!")
        assert False
    except ValueError as e:
        print(f"    ✅ SUCCESS: Caught expected error: {e}")
        assert "must be unlocked" in str(e)
        
    # 4. Cleanup
    db.query(PassengerDetails).filter(PassengerDetails.booking_id == booking.id).delete()
    db.delete(booking)
    db.delete(unlock_record)
    db.commit()
    
    print("\n✅ TASK 42 FULLY VERIFIED: Agent booking logic and enforcement are robust.")

if __name__ == "__main__":
    verify_task_42()
