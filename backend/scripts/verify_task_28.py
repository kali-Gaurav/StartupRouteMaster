import httpx
import asyncio
import time

async def verify():
    print("--- 📡 Task 28: Station Cold Spot Cross-Referencing Verification ---")
    
    url_base = "http://localhost:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS in a known Dead Zone
        # Western Ghats Tunnel: (19.7, 73.4) from our Task 2 bitmap
        print("\n[Step 1] Triggering SOS inside Western Ghats Tunnel (Dead Zone)...")
        payload = {
            "lat": 19.7, "lng": 73.4, 
            "name": "Deadzone User",
            "extra": "Help me"
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        print(f"Panic Score: {data.get('panic_score')}")
        print(f"Connectivity Status: {data.get('connectivity_status')}")
        
        if data.get("connectivity_status") == "CRITICAL_DEAD_ZONE":
            print("\n🏆 TASK 28 VERIFIED: Dead zone correctly detected and risk boosted.")
        else:
            print("\n❌ TASK 28 FAILED: System did not correlate location with dead zone.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
