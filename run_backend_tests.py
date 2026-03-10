import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_flow():
    print("--- 1. Testing Instant Startup (Fast Health Check) ---")
    try:
        res = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"Health Response ({res.status_code}): {res.json()}")
    except Exception as e:
        print(f"Health Check Failed: {e}")

    print("\n--- 2. Testing JIT Initialization (Heavy Request) ---")
    print("This will trigger Redis init and Graph warmup. Please wait...")
    start_time = time.time()
    try:
        # Trigger JIT via stats
        res = requests.get(f"{BASE_URL}/api/stats", timeout=60)
        duration = time.time() - start_time
        print(f"Stats Response ({res.status_code}) in {duration:.2f}s")
        print(json.dumps(res.json(), indent=2))
    except Exception as e:
        print(f"JIT Request Failed: {e}")

    print("\n--- 3. Testing CORS Headers ---")
    try:
        res = requests.options(f"{BASE_URL}/api/stats", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET"
        })
        print(f"CORS Options Status: {res.status_code}")
        print(f"Access-Control-Allow-Origin: {res.headers.get('Access-Control-Allow-Origin')}")
    except Exception as e:
        print(f"CORS Test Failed: {e}")

    print("\n--- 4. Verify JIT Persistence (Fast Second Request) ---")
    start_time = time.time()
    try:
        res = requests.get(f"{BASE_URL}/api/stats", timeout=5)
        duration = time.time() - start_time
        print(f"Stats (Second Hit) Response in {duration:.2f}s")
    except Exception as e:
        print(f"Second Hit Failed: {e}")

if __name__ == "__main__":
    # Give server time to bind
    time.sleep(3)
    test_flow()
