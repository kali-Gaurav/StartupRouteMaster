import httpx
import asyncio
import time

async def verify():
    print("--- 🛰️ Task 46: High-Frequency GPS 'Burst' Mode Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger High-Panic SOS
        # Text (+5), G-Force (+3) = Score 8+
        print("\n[Step 1] Triggering high-panic SOS to activate Burst Mode...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Burst User",
            "extra": "Help medical emergency now",
            "accel_g_force": 5.0
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        burst_ms = data.get("gps_burst_interval_ms")
        score = data.get("panic_score")
        print(f"Panic Score: {score}")
        print(f"GPS Burst Interval: {burst_ms}ms")
        
        if burst_ms == 2000:
            print("\n🏆 TASK 46 VERIFIED: 2-second GPS burst activated for high-panic incident.")
        else:
            print("\n❌ TASK 46 FAILED: Burst mode was not triggered.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
