import httpx
import asyncio
import time

async def verify():
    print("--- 🔋 Task 47: Battery-Critical Mode Verification ---")
    
    # 1. Trigger SOS
    url_sos = "http://localhost:8000/api/sos/"
    payload = {"lat": 28.6139, "lng": 77.2090, "name": "Battery Test User", "phone": "+91-5555555555"}
    
    async with httpx.AsyncClient() as client:
        res = await client.post(url_sos, json=payload)
        event_id = res.json().get("id")
        print(f"Created Event ID: {event_id}")
        
        # 2. Update with 10% Battery (Should hint Throttle)
        print("\n[Step 2] Sending 10% Battery update...")
        url_batt = f"http://localhost:8000/api/sos/{event_id}/battery"
        res_low = await client.post(url_batt, json={
            "battery_level": 0.10,
            "lat": 28.6139,
            "lng": 77.2090
        })
        print(f"Response: {res_low.json()}")

        # 3. Update with 2% Battery (Should trigger Last Breath)
        print("\n[Step 3] Sending 2% Battery update (Last Breath)...")
        res_crit = await client.post(url_batt, json={
            "battery_level": 0.02,
            "lat": 28.6145,
            "lng": 77.2100
        })

        data_crit = res_crit.json()
        print(f"Response: {data_crit}")

        # In the simplified logic, we just check if hint is TEXT_ONLY_LOW_POWER
        if data_crit.get("hint") == "TEXT_ONLY_LOW_POWER":
            print("\n🏆 BATTERY CRITICAL MODE VERIFIED: Last breath hint active.")
        else:
            print("\n❌ BATTERY CRITICAL MODE FAILED: Incorrect hints.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())