import sys
import os
import json
import uuid
import datetime
from jose import jwt

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.config import Config

def test_config_loading():
    print("\n--- 1. Testing Config Loading ---")
    try:
        Config.validate()
        print("✅ Config.validate() passed.")
    except Exception as e:
        print(f"❌ Config validation failed: {e}")
        # Check specifically for JWT Secret
        if not Config.SUPABASE_JWT_SECRET:
            print("❌ CRITICAL: SUPABASE_JWT_SECRET is missing or empty in .env")
        else:
             print(f"✅ SUPABASE_JWT_SECRET is loaded (len={len(Config.SUPABASE_JWT_SECRET)})")

def test_jwt_validation_logic():
    print("\n--- 2. Testing JWT Validation Logic ---")
    
    secret = Config.SUPABASE_JWT_SECRET
    if not secret:
        print("⚠️ Skipping JWT test because secret is missing.")
        return

    # Create a mock token
    user_id = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "email": "test@example.com",
        "aud": "authenticated",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        "iat": datetime.datetime.utcnow()
    }
    
    token = jwt.encode(payload, secret, algorithm="HS256")
    print(f"Generated Test Token: {token[:20]}...")

    # Decode it back using the logic from dependencies.py
    try:
        decoded = jwt.decode(
            token, 
            secret, 
            algorithms=["HS256"], 
            audience="authenticated",
            options={"verify_exp": True}
        )
        if decoded.get("sub") == user_id:
            print("✅ JWT Validation Logic: SUCCESS")
        else:
            print("❌ JWT Validation Logic: FAILED (ID mismatch)")
            
    except Exception as e:
        print(f"❌ JWT Validation Logic: FAILED with error: {e}")

if __name__ == "__main__":
    print("Running Authentication Configuration Verification...")
    test_config_loading()
    test_jwt_validation_logic()
    print("\nDone.")
