
import requests
import os

BASE_URL = "http://localhost:8000"

def test_task_2_cors():
    print("--- Testing Task 2: CORS Security ---")
    
    # 1. Test standard GET request CORS headers
    print("Step 1: Testing standard GET request...")
    origin = "http://localhost:5173"
    headers = {"Origin": origin}
    response = requests.get(f"{BASE_URL}/", headers=headers)
    
    allow_origin = response.headers.get("Access-Control-Allow-Origin")
    allow_creds = response.headers.get("Access-Control-Allow-Credentials")
    
    print(f"Origin: {origin} -> Access-Control-Allow-Origin: {allow_origin}")
    print(f"Access-Control-Allow-Credentials: {allow_creds}")
    
    # Credentials should be True, and Origin should NOT be '*' if creds are true
    assert allow_creds == "true"
    assert allow_origin != "*"
    
    # 2. Test Preflight OPTIONS request
    print("\nStep 2: Testing Preflight (OPTIONS)...")
    preflight_headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type, Authorization"
    }
    response = requests.options(f"{BASE_URL}/api/auth/logout", headers=preflight_headers)
    
    print(f"Preflight Status: {response.status_code}")
    print(f"Preflight Allow-Origin: {response.headers.get('Access-Control-Allow-Origin')}")
    print(f"Preflight Allow-Methods: {response.headers.get('Access-Control-Allow-Methods')}")
    print(f"Preflight Allow-Headers: {response.headers.get('Access-Control-Allow-Headers')}")
    
    assert response.status_code == 200
    assert "POST" in response.headers.get("Access-Control-Allow-Methods", "")
    assert "Authorization" in response.headers.get("Access-Control-Allow-Headers", "")

    # 3. Test Unauthorized Origin
    print("\nStep 3: Testing Unauthorized Origin...")
    bad_origin = "http://malicious-site.com"
    response = requests.get(f"{BASE_URL}/", headers={"Origin": bad_origin})
    
    allow_origin = response.headers.get("Access-Control-Allow-Origin")
    print(f"Bad Origin: {bad_origin} -> Access-Control-Allow-Origin: {allow_origin}")
    
    # If it's a "bad" origin, the header should either be missing or not match the bad origin
    assert allow_origin != bad_origin

    print("\n✅ Task 2 Verification: PRELIMINARY CHECKS COMPLETE")

if __name__ == "__main__":
    try:
        test_task_2_cors()
    except Exception as e:
        print(f"❌ Verification failed: {e}")
