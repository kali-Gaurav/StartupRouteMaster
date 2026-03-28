import requests
import json

url = "http://localhost:8000/api/v2/search/unified"
params = {
    "source": "NDLS",
    "destination": "KOTA",
    "date": "2026-03-30",
    "budget": "all",
    "multi_modal": "true",
    "limit": "50",
    "source_type": "live"
}

try:
    response = requests.get(url, params=params)
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response (text): {response.text}")
except Exception as e:
    print(f"Error: {e}")
