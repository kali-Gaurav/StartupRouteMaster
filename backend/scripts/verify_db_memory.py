import sys
import os
import uuid
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.chat import _load_session
from database import SessionLocal
from database.models import User, Profile

def test_db_memory():
    db = SessionLocal()
    user_id = str(uuid.uuid4())
    session_id = f"test-sess-{user_id}"
    
    print("--- Persistent AI Memory Verification ---")
    
    try:
        # 1. Create Mock User and Profile with AI Memory
        user = User(id=user_id, email=f"test_{user_id[:8]}@example.com")
        profile = Profile(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name="Test User",
            ai_memory={"preferred_class": "2A", "last_destination": "Mumbai"}
        )
        db.add(user)
        db.add(profile)
        db.commit()
        
        print(f"\n[Test] Loading session for User ID: {user_id}...")
        session = _load_session(session_id, user_id=user_id)
        
        # 2. Verify merge
        context = session.get("context", {})
        print(f"Loaded Context: {context}")
        
        if context.get("preferred_class") == "2A":
            print("[PASS] Persistent AI memory successfully merged into session.")
        else:
            print("[FAIL] AI memory merge failed.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        db.query(Profile).filter(Profile.user_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    test_db_memory()
