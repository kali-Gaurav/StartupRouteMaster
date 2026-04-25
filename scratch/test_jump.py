import requests
import json
import time

def test_grand_jump():
    url = "http://localhost:8000/api/v3/search/unified"
    params = {
        "source": "KOTA",
        "destination": "BLR",
        "date": "2025-05-15",
        "multi_modal": "true",
        "engine_model": "ENSEMBLE"
    }
    
    print(f"Triggering Grand Jump Search: KOTA -> BLR on 2025-05-15")
    start = time.time()
    try:
        response = requests.get(url, params=params, timeout=30)
        latency = (time.time() - start) * 1000
        print(f"Response received in {latency:.2f}ms (Status: {response.status_code})")
        
        if response.status_code == 200:
            data = response.json()
            journeys = data.get("data", {}).get("journeys", [])
            print(f"Found {len(journeys)} total journeys.")
            
            interlined = [j for j in journeys if j.get("metadata", {}).get("type") == "VIRTUAL_INTERLINED"]
            print(f"Interlined Jump Routes: {len(interlined)}")
            
            for idx, j in enumerate(interlined[:3]):
                print(f"\n[Jump Route #{idx+1}]")
                print(f"  ID: {j['journey_id']}")
                print(f"  Transfers: {j['num_transfers']}")
                print(f"  Cost: INR {j['total_cost']}")
                for l_idx, leg in enumerate(j.get("legs", [])):
                    print(f"    Leg {l_idx+1}: {leg['from_station_code']} -> {leg['to_station_code']} ({leg['train_number']})")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_grand_jump()
