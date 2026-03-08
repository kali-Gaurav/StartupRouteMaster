import asyncio
import sys
import os
from unittest.mock import patch
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus
from services.agent_booking_service import AgentBookingService

async def verify_task_27():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 27 (TATKAL PRIORITY)")
    
    db = SessionLocal()
    user_id = "user27"
    route_id = "route27"
    
    # 0. Setup
    u = User(id=user_id, email="u27@ex.com")
    db.merge(u)
    
    # Need an UNLOCK record first
    unlock = Booking(id="U27", user_id=user_id, route_id=route_id, service_type="UNLOCK", is_unlocked=True, booking_details={})
    db.merge(unlock)
    db.commit()
    
    # 1. Test Priority Assignment during Tatkal Window
    print("  Mocking Tatkal Window = TRUE...")
    with patch('utils.geo_utils.is_tatkal_window', return_value=True):
        booking = AgentBookingService.create_booking_request(db, user_id, route_id, [], 500.0)
        
        print(f"    Booking Priority: {booking.priority}")
        assert booking.priority == 0
        print("    Priority 0 Assignment: OK")
        
    # 2. Test Priority Assignment OUTSIDE Tatkal Window
    print("\n  Mocking Tatkal Window = FALSE...")
    with patch('utils.geo_utils.is_tatkal_window', return_value=False):
        booking2 = AgentBookingService.create_booking_request(db, user_id, route_id, [], 500.0)
        
        print(f"    Booking Priority: {booking2.priority}")
        assert booking2.priority == 10
        print("    Priority 10 Assignment: OK")
        
    # 3. Cleanup
    db.query(Booking).filter(Booking.id.in_([booking.id, booking2.id, "U27"])).delete()
    db.commit()
    
    print("\n✅ TASK 27 FULLY VERIFIED: Tatkal priority is automatically injected based on window logic.")

if __name__ == "__main__":
    asyncio.run(verify_task_27())
