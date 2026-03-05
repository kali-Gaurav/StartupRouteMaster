import httpx
import asyncio
import time

async def verify():
    print("--- 💀 Task 55: SOS Auto-Escalation via 'Stillness' Heuristic Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger Initial SOS
        print("\n[Step 1] Triggering initial SOS...")
        res_init = await client.post(f"{url_base}/", json={"lat": 28.6, "lng": 77.2, "name": "Stillness User"})
        event_id = res_init.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. First ping with zero motion
        print("\n[Step 2] Sending 1st ping with zero motion...")
        await client.post(f"{url_base}/{event_id}/battery", json={
            "battery_level": 0.8, "lat": 28.6, "lng": 77.2, "motion_level": 0.0
        })
        
        # 3. Second ping with zero motion (Trigger)
        print("\n[Step 3] Sending 2nd consecutive ping with zero motion...")
        res_trig = await client.post(f"{url_base}/{event_id}/battery", json={
            "battery_level": 0.8, "lat": 28.6, "lng": 77.2, "motion_level": 0.0
        })
        print(f"Update Status: {res_trig.json().get('status')}")
        
        # 4. Verify Priority Elevation
        print("\n[Step 4] Verifying incident state...")
        res_get = await client.get(f"{url_base}/{event_id}")
        event = res_get.json()
        
        print(f"Final Priority: {event.get('priority')}")
        print(f"Extra Notes: {event.get('extra')}")
        
        if event.get("priority") == "critical" and "PROLONGED STILLNESS" in event.get("extra", ""):
            print("\n🏆 TASK 55 VERIFIED: Stillness heuristic triggered critical escalation.")
        else:
            print("\n❌ TASK 55 FAILED: Incident did not escalate after prolonged stillness.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
