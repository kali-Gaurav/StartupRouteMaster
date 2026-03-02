import asyncio
import httpx
import time
from datetime import datetime, timedelta
import urllib.parse

BASE_URL = "http://127.0.0.1:8000/api"

async def test_search(client, source, dest, date, label=""):
    print(f"\n--- Testing: {label} [{source} -> {dest}] ---")
    payload = {
        "source": source,
        "destination": dest,
        "date": date,
        "budget": "all",
        "multi_modal": False,
        "journey_type": "single"
    }
    start = time.time()
    resp = await client.post(f"{BASE_URL}/search/", json=payload)
    latency = (time.time() - start) * 1000
    
    if resp.status_code != 200:
        print(f"❌ Failed: HTTP {resp.status_code} - {resp.text}")
        return None

    data = resp.json()
    journeys = data.get("journeys", [])
    print(f"✅ Success in {latency:.2f}ms. Found {len(journeys)} routes.")
    
    # Analyze engines used
    engine_counts = {}
    for j in journeys:
        engine = j.get("engine_used", "UNKNOWN")
        engine_counts[engine] = engine_counts.get(engine, 0) + 1
        
    for engine, count in engine_counts.items():
        print(f"   -> Engine {engine}: {count} routes")
        
    if journeys:
        print(f"   -> Top Route: {journeys[0].get('journey_id')} | Transfers: {journeys[0].get('num_transfers')} | Engine: {journeys[0].get('engine_used')}")
        
    return data

async def run_verification():
    print("🚀 Starting Routing Pipeline Verification 🚀\n")
    
    # Use a Wednesday 3 days from now
    target_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    print(f"Target Search Date: {target_date}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Test 1: Direct Route (Expected: TURBO)
        await test_search(client, "NDLS", "BCT", target_date, "Major Hubs (Direct)")

        # Test 2: Order Validation / Reverse (Expected: Different trains or TURBO)
        await test_search(client, "BCT", "NDLS", target_date, "Reverse Hubs")

        # Test 3: 2-3 Transfers (Expected: FASTPATH or RAPTOR)
        await test_search(client, "PGT", "BNC", target_date, "South India (Transfers likely)")
        
        # Test 4: Same Station (Expected: Failure / Empty)
        await test_search(client, "NDLS", "NDLS", target_date, "Same Station")
        
        # Test 5: Cache Hit Test (Expected: Faster latency)
        print("\n--- Testing Cache Hit ---")
        start = time.time()
        await client.post(f"{BASE_URL}/search/", json={"source": "NDLS", "destination": "BCT", "date": target_date})
        print(f"✅ Cache Hit Latency: {(time.time() - start) * 1000:.2f}ms")
        
        # Test 6: Load Testing
        print("\n--- Simple Load Test (10 concurrent requests) ---")
        tasks = []
        for i in range(10):
            payload = {"source": "NDLS", "destination": "BCT", "date": target_date}
            tasks.append(client.post(f"{BASE_URL}/search/", json=payload))
            
        start_load = time.time()
        results = await asyncio.gather(*tasks)
        load_latency = (time.time() - start_load) * 1000
        successes = sum(1 for r in results if r.status_code == 200)
        print(f"✅ Load Test Completed in {load_latency:.2f}ms. {successes}/10 requests successful.")

if __name__ == "__main__":
    asyncio.run(run_verification())