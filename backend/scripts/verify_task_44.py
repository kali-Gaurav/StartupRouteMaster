import httpx
import asyncio
import time

async def verify():
    print("--- 📳 Task 44: Silent-Panic Vibration Pattern Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger Critical SOS
        print("\n[Step 1] Triggering critical SOS to check haptic pattern...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Haptic User",
            "extra": "Help!",
            "accel_g_force": 6.0 # Critical
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        pattern = data.get("vibration_pattern")
        print(f"Priority: {data.get('priority')}")
        print(f"Vibration Pattern: {pattern}")
        
        # Morse SOS pattern: 3 shorts, 3 longs, 3 shorts (Simplified here)
        if pattern and len(pattern) > 4 and data.get("priority") == "critical":
            print("\n🏆 TASK 44 VERIFIED: Discreet haptic feedback pattern delivered.")
        else:
            print("\n❌ TASK 44 FAILED: Pattern missing or incorrect for priority.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
