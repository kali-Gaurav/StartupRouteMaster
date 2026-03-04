import asyncio
import sys
import os
import uuid
import logging

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Configure logging
logging.basicConfig(level=logging.INFO)

from services.emergency.alert_manager import EmergencyAlertManager
from database.session import SessionLocal
from database.models import User, Booking, Profile

async def test_crowdsource():
    print("--- 📣 Crowdsourced Responder Ping Verification ---")
    db = SessionLocal()
    
    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())
    trip_id = 9999
    
    try:
        # 1. Setup Two Users on the same Trip
        user_a = User(id=user_a_id, email="victim@example.com", supabase_id="victim-123")
        user_b = User(id=user_b_id, email="responder@example.com", supabase_id="responder-456")
        
        booking_a = Booking(
            id=str(uuid.uuid4()), user_id=user_a_id, trip_id=trip_id,
            booking_status='confirmed', pnr_number='PNR-A', booking_details={}
        )
        booking_b = Booking(
            id=str(uuid.uuid4()), user_id=user_b_id, trip_id=trip_id,
            booking_status='confirmed', pnr_number='PNR-B', booking_details={}
        )
        
        db.add_all([user_a, user_b, booking_a, booking_b])
        db.commit()
        print(f"Created two users on Trip {trip_id}")

        manager = EmergencyAlertManager()
        
        # 2. Process SOS for User A
        sos_event = {
            "id": "crowd-test-1",
            "user_id": user_a_id,
            "lat": 28.6428, "lng": 77.2190,
            "trip": {"vehicle_number": "12628", "trip_id": trip_id, "coach": "S4"}
        }
        
        print("\n[Test] Processing SOS for User A and looking for User B...")
        # We call the internal method directly for testing
        await manager._alert_nearby_trusted_users(trip_id, "S4", user_a_id)
        
        print("\n[PASS] Check logs for 'Found 1 potential responders' and 'Sending high-priority push to User responder-456'")

    finally:
        db.query(Booking).filter(Booking.trip_id == trip_id).delete()
        db.query(User).filter(User.id.in_([user_a_id, user_b_id])).delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    asyncio.run(test_crowdsource())
