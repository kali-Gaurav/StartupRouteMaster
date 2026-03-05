import httpx
import asyncio
import time

async def verify():
    print("--- 🔌 Task 12: TCP Keep-Alive Optimization Verification ---")
    
    url_base = "http://localhost:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS
        print("\n[Step 1] Triggering SOS...")
        payload = {"lat": 28.6139, "lng": 77.2090, "name": "KeepAlive Test User"}
        res = await client.post(f"{url_base}/", json=payload)
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Update with Critical Battery (2%)
        print("\n[Step 2] Sending 2% Battery update (Triggering Keep-Alive optimization)...")
        res_crit = await client.post(f"{url_base}/{event_id}/battery", json={
            "battery_level": 0.02, "lat": 28.6139, "lng": 77.2090
        })
        data = res_crit.json()
        print(f"Response: {data}")
        
        # 3. Verify via dedicated endpoint
        print("\n[Step 3] Fetching keep-alive hint via dedicated endpoint...")
        res_hint = await client.get(f"{url_base}/{event_id}/keepalive")
        hint_data = res_hint.json()
        print(f"Keep-Alive Hint: {hint_data.get('keepalive_ms')} ms")
        
        if hint_data.get("keepalive_ms") == 300000:
            print("\n🏆 TASK 12 VERIFIED: TCP Keep-Alive dynamically optimized for battery safety.")
        else:
            print("\n❌ TASK 12 FAILED: Incorrect keep-alive interval returned.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
