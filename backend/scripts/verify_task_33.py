import httpx
import asyncio
import time
import uuid

async def verify():
    print("--- 🛰️ Task 33: BLE Mesh Sync Verification ---")
    
    url = "http://localhost:8000/api/sos/mesh-sync"
    orig_eid = f"offline-device-{uuid.uuid4().hex[:6]}"
    
    async with httpx.AsyncClient() as client:
        # 1. Simulate a nearby phone relaying an 'overheard' SOS
        print(f"\n[Step 1] Relaying overheard SOS for offline ID: {orig_eid}...")
        payload = {
            "original_event_id": orig_eid,
            "relayed_by_user_id": "relay-phone-abc",
            "rssi_strength": -65,
            "data": {
                "lat": 28.6139, "lng": 77.2090, 
                "name": "Offline Victim",
                "phone": "+91-0000000000",
                "extra": "Help requested offline"
            }
        }
        res = await client.post(url, json=payload)
        print(f"DEBUG: RAW Relay Response: {res.text}")
        data = res.json()
        print(f"Relay Status: {data.get('status')}")
        
        # 2. Verify creation via standard API
        print("\n[Step 2] Verifying incident existence via standard API...")
        res_get = await client.get(f"http://localhost:8000/api/sos/{orig_eid}")
        event = res_get.json()
        
        print(f"Extra Notes: {event.get('extra')}")
        
        if data.get("status") == "initiated_via_mesh" and "BLE MESH" in event.get('extra', ''):
            print("\n🏆 TASK 33 VERIFIED: Mesh-relayed alerts successfully processed.")
        else:
            print("\n❌ TASK 33 FAILED: Mesh relay did not initiate a valid SOS.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
