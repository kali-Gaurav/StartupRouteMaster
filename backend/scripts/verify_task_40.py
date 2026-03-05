import httpx
import asyncio
import time
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.session import SessionLocal
from database.models import User, Profile
from sqlalchemy import text

async def verify():
    print("--- 📝 Task 40: Multi-language Post-Incident Debrief Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos"
    db = SessionLocal()
    
    try:
        # 1. Create a Responder to reward
        u_resp = User(supabase_id="responder-to-reward", email="r@reward.com")
        db.add(u_resp)
        db.commit()
        p_resp = Profile(user_id=u_resp.id, karma_score=100)
        db.add(p_resp)
        db.commit()
        
        # 2. Trigger SOS and get ID
        print("\n[Step 1] Triggering SOS...")
        res = await httpx.AsyncClient().post(f"{url_base}/", json={"lat": 28.6139, "lng": 77.2090, "name": "Debrief User"})
        event_id = res.json().get("id")
        print(f"Event ID: {event_id}")
        
        # 3. Submit Debrief with Reward
        print("\n[Step 2] Submitting debrief and rewarding responder...")
        debrief_payload = {
            "rating": 5,
            "comment": "The person from S5 helped me very quickly!",
            "emotional_state": "relieved",
            "responder_ids": ["responder-to-reward"]
        }
        res_db = await httpx.AsyncClient().post(f"{url_base}/{event_id}/debrief", json=debrief_payload)
        print(f"Debrief Status: {res_db.json().get('status')}")
        
        # 4. Check Karma Increase
        db.expire_all() # Ensure fresh read
        updated_p = db.query(Profile).join(User, User.id == Profile.user_id).filter(User.supabase_id == "responder-to-reward").first()
        print(f"Final Karma Score: {updated_p.karma_score}")
        
        if updated_p.karma_score == 110:
            print("\n🏆 TASK 40 VERIFIED: Debrief submitted and responder karma rewarded.")
        else:
            print("\n❌ TASK 40 FAILED: Karma reward logic did not trigger.")
            
    finally:
        db.execute(text("DELETE FROM profiles WHERE user_id IN (SELECT id FROM users WHERE supabase_id = 'responder-to-reward')"))
        db.query(User).filter(User.supabase_id == "responder-to-reward").delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    asyncio.run(verify())
