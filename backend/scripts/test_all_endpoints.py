import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(name, method, path, data=None):
    url = f"{BASE_URL}{path}"
    print(f"Testing {name} - {method} {url}")
    try:
        start_time = time.time()
        req = urllib.request.Request(url, method=method)
        if data:
            req.data = json.dumps(data).encode('utf-8')
            req.add_header('Content-Type', 'application/json')
            
        res = urllib.request.urlopen(req, timeout=10)
        body = res.read().decode('utf-8')
        duration = time.time() - start_time
        print(f"âœ… SUCCESS ({duration:.2f}s) - HTTP {res.status}")
        return json.loads(body)
    except Exception as e:
        print(f"âŒ FAILED - {e}")
        return None

def run_tests():
    print("=== STARTING BACKEND TESTS ===\n")
    
    # 1. Health Check
    test_endpoint("Health Check", "GET", "/api/status/health")
    
    # 2. Station Search
    test_endpoint("Station Suggest", "GET", "/api/stations/suggest?q=NDLS&limit=5")
    
    # 3. Route Search (Legacy / Main Search API)
    search_data = {
        "source": "NDLS",
        "destination": "BCT",
        "date": "2026-03-05",
        "budget": "all",
        "multi_modal": False
    }
    routes_res = test_endpoint("Main Route Search", "POST", "/api/search/", search_data)
    
    # Verify Journeys
    if routes_res and 'journeys' in routes_res:
        num_journeys = len(routes_res['journeys'])
        print(f"   -> Successfully generated {num_journeys} journeys between NDLS and BCT.")
        if num_journeys > 0:
            first = routes_res['journeys'][0]
            print(f"   -> Example Journey: {first.get('journey_id')} - Transfers: {first.get('num_transfers')} - Legs: {len(first.get('legs', []))}")
    else:
        print("   -> ERROR: 'journeys' not found in response.")

    # 4. Unified Search V2
    unified_data = {
        "source": "NDLS",
        "destination": "BCT",
        "date": "2026-03-05"
    }
    unified_res = test_endpoint("Unified Search V2", "POST", "/api/v2/search/unified", unified_data)
    if unified_res and isinstance(unified_res, list):
         print(f"   -> Successfully returned {len(unified_res)} items from unified search.")

    print("\n=== TESTS COMPLETED ===")

if __name__ == "__main__":
    run_tests()