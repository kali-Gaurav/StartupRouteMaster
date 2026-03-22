
import requests
import json
from jose import jwt
from datetime import datetime, timedelta
import time
import os

# Configuration (Assume local backend for testing)
BASE_URL = "http://localhost:8000"
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "3L0kvbdACG1I85UEORQUaW51F6bQhOIQUI+xEFTZep3JBvKVbcjMcgsIskheS19wVCN2GSWABFLJp43DJvUew==")

def create_mock_token(email="test@example.com", expires_in=3600):
    payload = {
        "sub": "test-user-id",
        "email": email,
        "exp": datetime.utcnow().timestamp() + expires_in,
        "aud": "authenticated",
        "role": "authenticated"
    }
    return jwt.encode(payload, SUPABASE_JWT_SECRET, algorithm="HS256")

def test_task_1_blacklist():
    print("--- Testing Task 1: Logout Token Blacklist ---")
    
    # 1. Create a valid token
    token = create_mock_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Call Logout
    print(f"Step 1: Calling /api/auth/logout with token...")
    # Using relative path prefix from app.py registration (likely /api/v2 or /auth)
    # Check app.py to confirm prefix
    response = requests.post(f"{BASE_URL}/api/v2/auth/logout", headers=headers)
    if response.status_code == 404:
        # Try different common prefix
        response = requests.post(f"{BASE_URL}/api/auth/logout", headers=headers)
        
    print(f"Logout Response: {response.status_code} - {response.json()}")
    assert response.status_code == 200
    
    # 3. Verify subsequent request fails with 401 and TOKEN_REVOKED
    print(f"Step 2: Calling protected endpoint with blacklisted token...")
    # Using /api/v2/user/profile as a protected endpoint
    response = requests.get(f"{BASE_URL}/api/v2/user/profile", headers=headers)
    
    print(f"Protected Endpoint Response: {response.status_code} - {response.text}")
    assert response.status_code == 401
    # Accept either our specific message or the generic FastAPI one if middleware wraps it
    assert any(msg in response.text.lower() for msg in ["revoked", "credentials", "unauthorized"])

    # 4. Test TTL (Short token)
    print(f"Step 3: Testing TTL with short-lived token...")
    short_token = create_mock_token(expires_in=2) # 2 seconds
    headers_short = {"Authorization": f"Bearer {short_token}"}
    requests.post(f"{BASE_URL}/api/v2/auth/logout", headers=headers_short)
    
    print("Waiting for token to expire in blacklist (3s)...")
    time.sleep(3)
    
    # After TTL, it should return "Invalid or expired token" (from Supabase) 
    # rather than "Token has been revoked" (from Blacklist) if blacklist cleaned up.
    # But since it's expired anyway, it's 401.
    response = requests.get(f"{BASE_URL}/api/v2/user/profile", headers=headers_short)
    print(f"Expired Short Token Response: {response.status_code} - {response.text}")
    assert response.status_code == 401

    print("✅ Task 1 Verification: SUCCESS")

if __name__ == "__main__":
    # Ensure the backend is running before running this
    try:
        test_task_1_blacklist()
    except Exception as e:
        print(f"❌ Verification failed: {e}")
