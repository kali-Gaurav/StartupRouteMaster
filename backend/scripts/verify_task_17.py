import httpx
import asyncio
import time

async def verify():
    print("--- 📉 Task 17: Accelerometer-based Panic Validation Verification ---")
    
    url_base = "http://localhost:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS with HIGH G-force
        print("\n[Step 1] Triggering SOS with 5.0G impact force...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Sensor Fusion User",
            "extra": "I just fell down", # No critical keywords like 'rob'
            "accel_g_force": 5.0
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        print(f"Priority: {data.get('priority')}")
        print(f"Category: {data.get('category')}")
        print(f"Extra notes: {data.get('extra')}")
        
        if data.get("priority") == "critical" and "impact" in data.get("extra", "").lower():
            print("\n🏆 TASK 17 VERIFIED: High G-force correctly elevated priority via sensor fusion.")
        else:
            print("\n❌ TASK 17 FAILED: Sensor data did not impact threat classification.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
