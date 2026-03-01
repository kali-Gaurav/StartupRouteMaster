import requests
import json
import time

def test_endpoints():
    base_url = "http://localhost:8000"
    frontend_url = "http://localhost:5173"
    
    print(f"🚀 Starting Production-Grade Endpoint Connection Test")
    print(f"======================================================")
    
    # 1. Test Backend Health
    try:
        resp = requests.get(f"{base_url}/health")
        print(f"✅ Backend Health Check: {resp.status_code} {resp.json()}")
    except Exception as e:
        print(f"❌ Backend Health Check Failed: {e}")

    # 2. Test Station Search (mimics StationSearch.tsx)
    try:
        resp = requests.get(f"{base_url}/api/stations/search?query=DEL")
        stations = resp.json()
        print(f"✅ Station Search (DEL): {resp.status_code}, Found {len(stations)} stations")
    except Exception as e:
        print(f"❌ Station Search Failed: {e}")

    # 3. Test Route Search (mimics useRailwaySearch.ts)
    # Payload matches the RAPTOR engine requirements
    search_params = {
        "origin": "NDLS",
        "destination": "BCT",
        "date": "2026-03-05",
        "passengers": 1
    }
    try:
        print(f"🔍 Triggering Route Search: NDLS -> BCT...")
        resp = requests.post(f"{base_url}/api/routes/search", json=search_params)
        print(f"✅ Route Search Response: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            routes = data.get('routes', [])
            print(f"📊 Results: Found {len(routes)} optimal routes")
            if routes:
                print(f"✨ First Route Category: {routes[0].get('category')}")
                print(f"🛡️ First Route Safety Score: {routes[0].get('objectives', {}).get('safety_score')}")
    except Exception as e:
        print(f"❌ Route Search Failed: {e}")

    # 4. Test Frontend Accessibility
    try:
        resp = requests.get(frontend_url)
        print(f"✅ Frontend Dev Server: {resp.status_code} (Alive)")
    except Exception as e:
        print(f"❌ Frontend Dev Server Unreachable: {e}")

    print(f"======================================================")
    print(f"🎉 Connection Test Complete")

if __name__ == "__main__":
    # Give servers time to breathe
    print("⏳ Waiting for servers to initialize...")
    time.sleep(5)
    test_endpoints()
