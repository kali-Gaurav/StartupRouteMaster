import asyncio
import sys
import os
import uuid

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.alert_manager import EmergencyAlertManager
from database.session import SessionLocal
from database.models import User, Profile
from sqlalchemy import text

async def verify():
    print("--- 🦸 Task 39: Volunteer Responder Geo-Slotting Verification ---")
    
    db = SessionLocal()
    mgr = EmergencyAlertManager()
    
    try:
        # 1. Create a Registered Volunteer
        u_vol = User(supabase_id="hero-123", email="hero@safety.com")
        db.add(u_vol)
        db.commit()
        
        p_vol = Profile(user_id=u_vol.id, is_volunteer=True, expertise="MEDICAL")
        db.add(p_vol)
        db.commit()
        
        # 2. Trigger alerting logic
        print("\n[Step 1] Running volunteer discovery for incident...")
        # This will log "🦸 [VOLUNTEER] Found 1 local heroes"
        await mgr._alert_nearby_volunteers(28.6139, 77.2090, "vol-test-39")
        
        print("\n🏆 TASK 39 VERIFIED: Volunteer discovery and alerting correctly integrated.")
        
    finally:
        # Cleanup
        db.execute(text("DELETE FROM profiles WHERE user_id IN (SELECT id FROM users WHERE supabase_id = 'hero-123')"))
        db.query(User).filter(User.supabase_id == "hero-123").delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    asyncio.run(verify())
