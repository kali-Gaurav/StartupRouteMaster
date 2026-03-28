
import requests
import json
import time
from datetime import datetime, timedelta

def test_search_yield():
    url = "http://localhost:8000/api/search/"
    
    # 2026-04-02 was the date used in test_all_engines.py
    travel_date = "2026-04-02"
    
    pairs = [
        ("NDLS", "MMCT"),
        ("HWH", "MAS"),
        ("SBC", "PUNE")
    ]
    
    print(f"🚀 Testing Integrated Search Endpoint Yield (Date: {travel_date})")
    
    for src, dst in pairs:
        print(f"\n📍 Searching {src} -> {dst}...")
        payload = {
            "source": src,
            "destination": dst,
            "date": travel_date,
            "budget": "standard",
            "quota": "GN"
        }
        
        start = time.time()
        try:
            response = requests.post(url, json=payload, timeout=30)
            duration = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                journeys = data.get("data", {}).get("journeys", [])
                total = data.get("total_available", 0)
                
                engines_used = set()
                transfer_counts = {}
                
                for j in journeys:
                    eng = j.get("metadata", {}).get("engine", "unknown")
                    engines_used.add(eng)
                    
                    t_count = len(j.get("transfers", []))
                    transfer_counts[t_count] = transfer_counts.get(t_count, 0) + 1
                
                print(f" ✅ Success in {duration:.2f}ms. Found {len(journeys)} journeys (Total Avail: {total})")
                print(f" 🛠 Engines involved: {', '.join(engines_used)}")
                print(f" 🔄 Transfers breakdown: {transfer_counts}")
                
                if len(journeys) == 0:
                    print(" ⚠️ WARNING: Zero journeys found! Check if backend is running and data is loaded.")
            else:
                print(f" ❌ Failed with status {response.status_code}: {response.text}")
        except Exception as e:
            print(f" ❌ Error connecting to backend: {e}")
            print(" Make sure the backend is running at http://localhost:8000")

if __name__ == "__main__":
    test_search_yield()
