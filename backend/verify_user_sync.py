import asyncio
import sys
import os
import uuid
from jose import jwt

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionUser
from database.models import User, Profile
from dependencies import get_current_user
from database.config import Config

async def test_user_sync():
    print("\n--- 3. Testing User Sync Logic ---")
    
    db = SessionUser()
    try:
        # 1. Create a mock token
        supabase_id = f"test-user-{uuid.uuid4()}"
        email = "test-sync@example.com"
        secret = Config.SUPABASE_JWT_SECRET
        
        payload = {
            "sub": supabase_id,
            "email": email,
            "aud": "authenticated"
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        auth_header = f"Bearer {token}"
        
        print(f"Simulating login for {email} (ID: {supabase_id})...")
        
        # 2. Call get_current_user
        user = await get_current_user(authorization=auth_header, db=db)
        
        # 3. Verify in DB
        db_user = db.query(User).filter(User.supabase_id == supabase_id).first()
        if db_user:
            print(f"✅ User record created in DB (ID: {db_user.id})")
            
            db_profile = db.query(Profile).filter(Profile.user_id == db_user.id).first()
            if db_profile:
                print(f"✅ Profile record created in DB")
            else:
                print(f"❌ Profile record MISSING")
        else:
            print(f"❌ User record MISSING in DB")
            
        # 4. Test re-sync (should not create duplicate)
        print("Simulating second login for same user...")
        user2 = await get_current_user(authorization=auth_header, db=db)
        if user2.id == user.id:
            print("✅ Re-sync successful (No duplicate created)")
        else:
            print("❌ Re-sync FAILED (Duplicate created?)")

        # Cleanup test data
        db.delete(db_profile)
        db.delete(db_user)
        db.commit()
        print("Test data cleaned up.")

    except Exception as e:
        print(f"❌ User Sync Test FAILED: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_user_sync())
