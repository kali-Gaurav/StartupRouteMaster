import sys
import os
import urllib.parse
from datetime import datetime

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus
from services.agent_booking_service import AgentBookingService
from utils.payment_utils import generate_upi_uri

def verify_task_3():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 3 (AMOUNT LOCKING)")
    
    db = SessionLocal()
    user_id = "user-task-3"
    route_id = "route-task-3"
    
    # 0. Setup
    u = User(id=user_id, email="u3@ex.com")
    db.merge(u)
    
    # Need an UNLOCK record first
    unlock = Booking(id="U3", user_id=user_id, route_id=route_id, service_type="UNLOCK", is_unlocked=True, booking_details={})
    db.merge(unlock)
    db.commit()
    
    # 1. Test Locked Amount Creation
    print("  Creating booking request with 1500.555 fare...")
    ticket_fare = 1500.555
    passengers = [] # Empty for this test
    
    booking = AgentBookingService.create_booking_request(db, user_id, route_id, passengers, ticket_fare)
    
    print(f"    Booking Amount Paid: {booking.amount_paid}")
    print(f"    Details Snapshot: {booking.booking_details['ticket_fare']}")
    
    # Check rounding
    # 1500.555 + 10 = 1510.555 -> 1510.56
    assert booking.amount_paid == 1510.56
    assert booking.booking_details["ticket_fare"] == 1500.56
    
    # 2. Verify UPI URI consistency
    uri = generate_upi_uri("vpa@upi", "Name", booking.amount_paid, "Note")
    parsed = urllib.parse.urlparse(uri)
    query = urllib.parse.parse_qs(parsed.query)
    
    print(f"    URI Amount: {query['am'][0]}")
    assert query["am"][0] == "1510.56"
    
    # 3. Cleanup
    db.query(Booking).filter(Booking.id.in_([booking.id, "U3"])).delete(synchronize_session=False)
    db.commit()
    
    print("\n✅ TASK 3 FULLY VERIFIED: Dynamic amount locking and rounding are perfect.")

if __name__ == "__main__":
    verify_task_3()
