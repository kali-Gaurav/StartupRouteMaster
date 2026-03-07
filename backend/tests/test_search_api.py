import httpx
import sys
from datetime import datetime, timedelta

def test_search_api():
    url = "http://localhost:8000/api/v2/search/unified"
    
    # Use PGT to KOTA for tomorrow
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    params = {
        "source": "PGT",
        "destination": "KOTA",
        "date": tomorrow,
        "budget": "budget"
    }
    
    print(f"Testing Search API: {params}")
    
    try:
        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=60.0)
            if response.status_code == 200:
                data = response.json()
                print("✅ Search API Success!")
                print(f"  Source: {data.get('source')}")
                print(f"  Destination: {data.get('destination')}")
                print(f"  Total Journeys: {len(data.get('journeys', []))}")
                
                grouped = data.get('grouped_journeys', {})
                print(f"  Direct: {len(grouped.get('direct', []))}")
                print(f"  One Transfer: {len(grouped.get('one_transfer', []))}")
                print(f"  Most Optimal: {len(grouped.get('most_optimal', []))}")
                
                if grouped.get('most_optimal'):
                    best = grouped['most_optimal'][0]
                    print(f"  Best Route: {best.get('journey_id')} | Fare: ₹{best.get('total_fare')}")
                
                return True
            else:
                print(f"❌ Search API Failed with status {response.status_code}")
                print(f"  Response: {response.text}")
                return False
    except Exception as e:
        print(f"❌ Error during Search API test: {e}")
        return False

if __name__ == "__main__":
    if not test_search_api():
        sys.exit(1)
