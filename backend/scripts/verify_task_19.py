import httpx
import asyncio
import time

async def verify():
    print("--- 🚨 Task 19: Fall Detection & Sudden Impact Heuristics Verification ---")
    
    url_base = "http://localhost:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS with "True Fall" Heuristic (High G + Stillness)
        print("\n[Step 1] Triggering SOS with 5.0G impact and 0.05 post-impact motion (Stillness)...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Heuristic Test User",
            "accel_g_force": 5.0,
            "post_impact_motion": 0.05 # Near zero
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        print(f"Priority: {data.get('priority')}")
        print(f"Category: {data.get('category')}")
        print(f"Notes: {data.get('extra')}")
        
        if data.get("category") == "medical_emergency_fall" and data.get("priority") == "critical":
            print("\n🏆 TASK 19 VERIFIED: True Fall correctly identified via heuristics.")
        else:
            print("\n❌ TASK 19 FAILED: Heuristics did not correctly categorize the fall.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
