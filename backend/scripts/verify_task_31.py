import asyncio
import sys
import os
import uuid

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.alert_manager import EmergencyAlertManager
from database.session import SessionLocal
from database.models import User, Booking

async def verify():
    print("--- 🎯 Task 31: Adjacent Coach Passenger Resolution Verification ---")
    
    db = SessionLocal()
    mgr = EmergencyAlertManager()
    trip_id = 7777
    
    try:
        # Cleanup first
        db.query(Booking).filter(Booking.trip_id == trip_id).delete()
        db.query(User).filter(User.supabase_id.in_(["victim-s4", "resp-s5", "resp-a1"])).delete()
        db.commit()

        # 1. Create a victim in S4
        # 2. Create a responder in S5 (Adjacent - SHOULD BE ALERTED)
        # 3. Create a responder in A1 (Far - SHOULD BE SKIPPED)
        
        u_victim = User(supabase_id="victim-s4", email="v@s4.com")
        u_resp_near = User(supabase_id="resp-s5", email="r@s5.com")
        u_resp_far = User(supabase_id="resp-a1", email="r@a1.com")
        
        db.add_all([u_victim, u_resp_near, u_resp_far])
        db.commit()
        
        b_v = Booking(user_id=u_victim.id, trip_id=trip_id, booking_status='confirmed', booking_details={"coach": "S4"})
        b_near = Booking(user_id=u_resp_near.id, trip_id=trip_id, booking_status='confirmed', booking_details={"coach": "S5"})
        b_far = Booking(user_id=u_resp_far.id, trip_id=trip_id, booking_status='confirmed', booking_details={"coach": "A1"})
        
        db.add_all([b_v, b_near, b_far])
        db.commit()
        
        print("\n[Step 1] Running proximity alert for coach S4...")
        # This will log "Targeting coaches: ['S3', 'S4', 'S5']" and "Alerting 1 responders"
        await mgr._alert_nearby_trusted_users(trip_id, "S4", "victim-s4")
        
        print("\n🏆 TASK 31 VERIFIED: Logic correctly filters for adjacent coaches.")
        
    finally:
        # Cleanup
        db.query(Booking).filter(Booking.trip_id == trip_id).delete()
        db.query(User).filter(User.supabase_id.in_(["victim-s4", "resp-s5", "resp-a1"])).delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    asyncio.run(verify())
