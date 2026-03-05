import httpx
import asyncio
import time
import uuid
import base64

async def verify():
    print("--- 📁 Task 34: WiFi-Direct Ad-Hoc SOS Propagation Verification ---")
    
    url = "http://localhost:8000/api/sos/mesh-sync"
    orig_eid = f"wifi-direct-{uuid.uuid4().hex[:6]}"
    
    # Mock high-fidelity data (e.g. compressed voice transcript)
    mock_large_data = base64.b64encode(b"This is a high-fidelity voice transcript relayed via WiFi-Direct.").decode('utf-8')
    
    async with httpx.AsyncClient() as client:
        # 1. Simulate a nearby phone relaying a large payload
        print(f"\n[Step 1] Relaying large WiFi-Direct payload for ID: {orig_eid}...")
        payload = {
            "original_event_id": orig_eid,
            "relayed_by_user_id": "bridge-device-xyz",
            "rssi_strength": -45, # Strong signal (WiFi proximity)
            "data": {
                "lat": 28.6139, "lng": 77.2090, 
                "name": "Offline User",
                "phone": "+91-1111111111",
                "extra": "Help"
            },
            "large_payload_b64": mock_large_data
        }
        res = await client.post(url, json=payload)
        data = res.json()
        print(f"Relay Status: {data.get('status')}")
        
        # 2. Verify creation and flag via standard API
        print("\n[Step 2] Verifying high-fidelity flag in incident notes...")
        res_get = await client.get(f"http://localhost:8000/api/sos/{orig_eid}")
        event = res_get.json()
        
        print(f"Extra Notes: {event.get('extra')}")
        
        if "HIGH-FIDELITY" in event.get('extra', ''):
            print("\n🏆 TASK 34 VERIFIED: WiFi-Direct relayed large payloads successfully handled.")
        else:
            print("\n❌ TASK 34 FAILED: System missed the high-fidelity data flag.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
