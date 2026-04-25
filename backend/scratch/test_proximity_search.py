import asyncio
import httpx
import json
import time

async def stress_test_proximity():
    """
    Stress Test: GZB (Ghaziabad) -> CSMT (Mumbai)
    GZB has fewer direct trains than NDLS. 
    This should trigger 'Proximity Discovery' to check NDLS or NZM.
    """
    base_url = "http://localhost:8000"
    search_payload = {
        "source": "GZB",
        "destination": "CSMT",
        "travel_date": "2024-12-25", # Peak season date
        "budget_category": "comfort",
        "quota": "GN"
    }

    print(f"🚀 Starting Stress Test: Proximity Recovery ({search_payload['source']} -> {search_payload['destination']})")
    
    start_time = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(f"{base_url}/api/v3/search", json=search_payload)
            latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                journeys = data.get("data", {}).get("journeys", [])
                metadata = data.get("metadata", {})
                
                print(f"✅ Success! Found {len(journeys)} journeys in {latency:.2f}ms")
                
                # Check for proximity triggers [Point 6]
                proximity_count = sum(1 for j in journeys if j.get("metadata", {}).get("is_proximity_alt"))
                print(f"🔍 Proximity Suggestions: {proximity_count}")
                
                for j in journeys[:3]:
                    orig = j["segments"][0]["from"]
                    dest = j["segments"][-1]["to"]
                    alt_reason = j.get("metadata", {}).get("alt_reason", "N/A")
                    print(f"  - [{orig} -> {dest}] {alt_reason}")
                
                if proximity_count > 0:
                    print("🏆 TEST PASSED: Proximity Recovery logic triggered and yielded results.")
                else:
                    print("⚠️ TEST WARNING: No proximity alternatives found. Check if direct trains exist for GZB.")
                    
            else:
                print(f"❌ Failed: HTTP {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(stress_test_proximity())
