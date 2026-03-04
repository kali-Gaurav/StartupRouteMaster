import httpx
import asyncio
import os
import json
import time

async def verify():
    print("--- 🌍 Multi-Region Failover: Local Persistence Verification ---")
    
    # Matching the logic in api/sos.py for absolute path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_file = os.path.join(base_dir, "emergency_cache.json")
    
    print(f"DEBUG: Looking for cache at {cache_file}")
    if os.path.exists(cache_file):
        os.remove(cache_file)
        
    # 1. Trigger SOS
    url = "http://localhost:8000/api/sos/"
    payload = {"lat": 22.5726, "lng": 88.3639, "name": "Failover User", "phone": "+91-1111111111"}
    
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=payload)
        event_id = res.json().get("id")
        print(f"Created Event ID: {event_id}")
        
        # 2. Wait for file write
        time.sleep(2)
        
        # 3. Check if file exists and has the event
        if os.path.exists(cache_file):
            print(f"✅ SUCCESS: {cache_file} was created.")
            with open(cache_file, 'r') as f:
                data = json.load(f)
                if any(e['id'] == event_id for e in data):
                    print(f"🏆 FAILOVER VERIFIED: Event {event_id} persisted to local file.")
                else:
                    print("❌ FAILOVER FAILED: Event not found in local file.")
        else:
            print(f"❌ FAILOVER FAILED: {cache_file} not found.")

if __name__ == "__main__":
    asyncio.run(verify())