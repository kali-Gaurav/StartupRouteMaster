import asyncio
import sys
import os
import uuid

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.session import SessionLocal
from database.models import User, UserAIPreference

async def test_localized_voice():
    print("--- 🌍 Multi-lingual Voice Triage Verification ---")
    db = SessionLocal()
    user_id = str(uuid.uuid4())
    
    try:
        # 1. Setup Hindi User
        user = User(id=user_id, email=f"hi_{user_id[:8]}@example.com")
        pref = UserAIPreference(
            id=str(uuid.uuid4()),
            user_id=user_id,
            preferred_language="hi"
        )
        db.add(user)
        db.add(pref)
        db.commit()
        print(f"Created Hindi-preferring user: {user_id}")

        # 2. Call Triage Start
        from api.voice_triage import voice_triage_start
        print("\n[Test] Fetching TwiML for Hindi user...")
        twiml = await voice_triage_start(user_id=user_id)
        
        print(f"TwiML Snippet: {twiml[:150]}...")
        
        if "यह रूट मास्टर इमरजेंसी है" in twiml and "hi-IN-Wavenet-A" in twiml:
            print("\n🏆 LOCALIZED VOICE VERIFIED: Hindi prompt and voice selected correctly.")
        else:
            print("\n❌ FAIL: Hindi localization missing in TwiML.")

    finally:
        db.query(UserAIPreference).filter(UserAIPreference.user_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    asyncio.run(test_localized_voice())
