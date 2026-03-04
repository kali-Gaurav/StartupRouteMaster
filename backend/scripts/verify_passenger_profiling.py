import asyncio
import sys
import os
import uuid
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.alert_manager import EmergencyAlertManager
from database.session import SessionLocal
from database.models import User, Profile

async def test_passenger_profiling():
    print("--- 👤 Passenger High-Risk Profiling Verification ---")
    
    db = SessionLocal()
    user_id = str(uuid.uuid4())
    
    try:
        # 1. Setup Mock High-Risk Profile
        user = User(id=user_id, email=f"high_risk_{user_id[:8]}@example.com")
        profile = Profile(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name="Emergency Test User",
            blood_group="O+",
            medical_conditions="Diabetes",
            is_high_risk_passenger=True
        )
        db.add(user)
        db.add(profile)
        db.commit()
        print(f"Created high-risk user: {user_id}")

        manager = EmergencyAlertManager()
        
        # Simulate SOS
        sos_event = {
            "id": "prof-test-1",
            "user_id": user_id,
            "lat": 28.6428,
            "lng": 77.2190,
            "extra": "User feels dizzy",
            "chat_history": []
        }
        
        print("\n[Test] Processing SOS for High-Risk User...")
        res = await manager.process_sos_alert(sos_event)
        
        prof_data = res.get("passenger_profile", {})
        
        print(f"Category: {res.get('category')}")
        print(f"Priority: {res.get('priority')}")
        print(f"Attached Blood Group: {prof_data.get('blood_group')}")
        print(f"Attached Medical Conditions: {prof_data.get('medical_conditions')}")
        print(f"High Risk Flag: {prof_data.get('is_high_risk')}")
        
        if res.get('priority') == 'critical' and prof_data.get('blood_group') == 'O+':
            print("\n🏆 PASSENGER PROFILING VERIFIED: User data correctly attached and priority escalated.")
        else:
            print("\n❌ VERIFICATION FAILED: Profile data missing or priority not escalated.")

    finally:
        # Cleanup
        db.query(Profile).filter(Profile.user_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    asyncio.run(test_passenger_profiling())
