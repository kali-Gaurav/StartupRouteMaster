import httpx
import asyncio
import time

async def verify():
    print("--- 💀 Task 53: Battery-Critical 'Last Breath' Priority Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger Initial Low Priority SOS
        print("\n[Step 1] Triggering initial SOS...")
        res_init = await client.post(f"{url_base}/", json={"lat": 28.6, "lng": 77.2, "name": "Battery User"})
        event_id = res_init.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Update with Critical Battery (1%)
        print("\n[Step 2] Sending 1% battery update (Last Breath)...")
        battery_payload = {
            "battery_level": 0.01,
            "lat": 28.6001,
            "lng": 77.2001,
            "is_last_breath": True
        }
        res_batt = await client.post(f"{url_base}/{event_id}/battery", json=battery_payload)
        data = res_batt.json()
        print(f"Battery Update Response: {data}")
        
        # 3. Verify Priority Elevation
        print("\n[Step 3] Verifying incident state...")
        res_get = await client.get(f"{url_base}/{event_id}")
        event = res_get.json()
        
        print(f"Final Priority: {event.get('priority')}")
        print(f"Extra Notes: {event.get('extra')}")
        
        if event.get("priority") == "critical" and "LAST BREATH" in event.get("extra", ""):
            print("\n🏆 TASK 53 VERIFIED: 'Last Breath' priority boost and sync confirmed.")
        else:
            print("\n❌ TASK 53 FAILED: Priority did not elevate or flag missing.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
