import httpx
import asyncio
import time

async def verify():
    print("--- 📞 Task 43: Emergency Conference Call Bridge Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger Critical SOS
        print("\n[Step 1] Triggering critical SOS to initiate bridge...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Bridge User",
            "phone": "+91-8888888888",
            "extra": "Medical emergency! Heart attack!",
            "accel_g_force": 5.0 # Boost to critical
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        conf_id = data.get("conference_id")
        print(f"Conference ID: {conf_id}")
        print(f"Priority: {data.get('priority')}")
        
        if conf_id and conf_id.startswith("CONF-") and data.get("priority") == "critical":
            print("\n🏆 TASK 43 VERIFIED: Emergency audio bridge initiated for critical incident.")
        else:
            print("\n❌ TASK 43 FAILED: Bridge was not created or incident priority too low.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
