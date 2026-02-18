#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

# Tomorrow's date
tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

# Test data
search_request = {
    "source": "Delhi",
    "destination": "Palakkad",
    "date": tomorrow,
    "budget": "standard"
}

print(f"🚀 Searching routes from {search_request['source']} to {search_request['destination']} on {tomorrow}")
print("=" * 80)

try:
    # Try the POST /api/search endpoint
    response = requests.post(
        f"{BASE_URL}/api/search",
        json=search_request,
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response:\n")
    
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2))
    else:
        print(response.text)
        
except Exception as e:
    print(f"Error: {e}")
    print(f"\nTrying to check available endpoints...")
    
    try:
        # Check if API is responding
        health = requests.get(f"{BASE_URL}/docs", timeout=5)
        if health.status_code == 200:
            print("✓ Backend is running at http://localhost:8000")
            print("✓ Swagger UI available at http://localhost:8000/docs")
        else:
            print(f"Backend returned status: {health.status_code}")
    except Exception as e2:
        print(f"Cannot reach backend: {e2}")
