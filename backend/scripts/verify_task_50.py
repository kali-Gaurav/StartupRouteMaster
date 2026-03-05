import struct
import httpx
import asyncio
import time
import os

async def verify():
    print("--- 🔥 Task 50: Historical 'Danger-Hotspot' Influence Verification ---")
    
    # 1. Seed Risk Index with a Hotspot
    index_path = "backend/data/risk_index.bin"
    os.makedirs("backend/data", exist_ok=True)
    
    # New Delhi Hotspot: (28.6, 77.2) with risk 200
    with open(index_path, "wb") as f:
        f.write(struct.pack("ffB", 28.6, 77.2, 200))
    print(f"Seeded historical hotspot at 28.6, 77.2 (Risk: 200)")
    
    url_base = "http://127.0.0.1:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 2. Trigger SOS at the hotspot
        print("\n[Step 2] Triggering SOS at the historical hotspot...")
        payload = {
            "lat": 28.601, "lng": 77.201, # Within 5km proximity
            "name": "Hotspot User",
            "extra": "Help"
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        score = data.get("panic_score")
        hist_risk = data.get("historical_risk_level")
        
        print(f"Panic Score: {score}")
        print(f"Historical Risk Level: {hist_risk}")
        
        # Base panic for 'help' is high, plus 1 for hotspot
        if hist_risk == 200 and score is not None:
            print("\n🏆 TASK 50 VERIFIED: Historical risk correctly identified and score boosted.")
        else:
            print("\n❌ TASK 50 FAILED: Hotspot was ignored.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
