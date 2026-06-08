import requests
import json
import time

def test_unified_search():
    url = "http://127.0.0.1:8000/api/v3/search/unified"
    params = {
        "source": "NDLS",
        "destination": "BCT",
        "date": "2026-04-25",
        "persona": "ECONOMY",
        "tier": "ELITE"
    }
    
    print(f"Sending request to {url}...")
    start_time = time.time()
    try:
        response = requests.get(url, params=params, timeout=300)
        duration = time.time() - start_time
        
        print(f"Request took {duration:.2f} seconds")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # V3 returns 'data' which contains 'journeys'
            journeys = data.get('data', {}).get('journeys', [])
            print(f"Success! Found {len(journeys)} journeys.")
            if journeys:
                first = journeys[0]
                print(f"First Journey: {first.get('train_name', 'No name')} ({first.get('train_number', 'N/A')})")
                print(f"Fare: {first.get('fare', 'N/A')}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_unified_search()
