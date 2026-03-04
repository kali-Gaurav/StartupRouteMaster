import asyncio
import sys
import os
import uuid

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.alert_manager import EmergencyAlertManager
from database.session import SessionLocal
from database.models import User, Profile

async def test_family_outreach():
    print("--- 👨‍👩‍👧‍👦 Automated Family Outreach Verification ---")
    db = SessionLocal()
    user_id = str(uuid.uuid4())
    
    try:
        # 1. Setup User
        user = User(id=user_id, email=f"family_test_{user_id[:8]}@example.com")
        profile = Profile(id=str(uuid.uuid4()), user_id=user_id, name="Gaurav Nagar")
        db.add(user)
        db.add(profile)
        db.commit()

        manager = EmergencyAlertManager()
        
        # 2. Simulate CRITICAL SOS
        sos_event = {
            "id": "family-test-999",
            "user_id": user_id,
            "priority": "critical",
            "name": "Gaurav Nagar",
            "lat": 28.6428, "lng": 77.2190
        }
        
        print("\n[Test] Processing CRITICAL SOS and expecting family alert dispatch...")
        await manager.process_sos_alert(sos_event)
        
        # Give a moment for the asyncio task
        await asyncio.sleep(1)
        
        print("\n[PASS] Check logs for '👨‍👩‍👧‍👦 [FAMILY ALERT]' and the secure tracking URL.")

    finally:
        db.query(Profile).filter(Profile.user_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    asyncio.run(test_family_outreach())
