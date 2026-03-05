import httpx
import asyncio
import time

async def verify():
    print("--- 📍 Task 5: Location Delta-Encoding Verification ---")
    
    url_base = "http://localhost:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS (First Point - Anchor)
        print("\n[Step 1] Triggering SOS (Anchor point)...")
        payload = {"lat": 28.6139, "lng": 77.2090, "name": "Delta Test User"}
        res = await client.post(f"{url_base}/", json=payload)
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Simulate Movement (Should trigger Deltas)
        # Point 2: +0.001 lat
        print("[Step 2] Updating location (+0.001 lat)...")
        await client.post(f"{url_base}/{event_id}/battery", json={
            "battery_level": 0.9, "lat": 28.6149, "lng": 77.2090
        })
        
        # Point 3: +0.002 lat, +0.001 lng
        print("[Step 3] Updating location (+0.002 lat, +0.001 lng)...")
        await client.post(f"{url_base}/{event_id}/battery", json={
            "battery_level": 0.8, "lat": 28.6159, "lng": 77.2100
        })
        
        # 3. Fetch SOS and verify reconstruction
        print("\n[Step 4] Fetching incident to verify reconstruction...")
        res_get = await client.get(f"{url_base}/all")
        event = next((e for e in res_get.json() if e['id'] == event_id), None)
        
        if event:
            history = event.get("location_history", [])
            print(f"Total points in history: {len(history)}")
            for i, p in enumerate(history):
                print(f"  Point {i}: {p['lat']}, {p['lng']} (Is Decoded: {p.get('is_decoded', False)})")
            
            if len(history) >= 3 and history[-1]['lat'] == 28.6159:
                print("\n🏆 TASK 5 VERIFIED: Deltas successfully stored and reconstructed.")
            else:
                print("\n❌ TASK 5 FAILED: History mismatch or reconstruction failed.")
        else:
            print("❌ Failure: Could not find event via API.")

if __name__ == "__main__":
    # Server should be auto-reloaded via uvicorn if reload=True
    # But we'll give it a moment
    time.sleep(5)
    asyncio.run(verify())
