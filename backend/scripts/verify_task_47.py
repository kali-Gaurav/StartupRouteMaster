import httpx
import asyncio
import time

async def verify():
    print("--- 🛰️ Task 47: Predictive-Pre-fetch for Dead-Zones Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos/"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Trigger SOS in a Dead Zone
        print("\n[Step 1] Triggering SOS in Western Ghats Tunnel (Dead Zone)...")
        payload = {
            "lat": 19.7, "lng": 73.4, 
            "name": "Pre-fetch User",
            "extra": "Help"
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        pre_fetch = data.get("pre_fetch_data")
        print(f"Pre-fetch Data present: {pre_fetch is not None}")
        
        if pre_fetch and len(pre_fetch.get("offline_authorities", [])) > 0:
            print("\n🏆 TASK 47 VERIFIED: Predictive data bundled for upcoming dead zone.")
        else:
            print("\n❌ TASK 47 FAILED: No pre-fetch data received.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
