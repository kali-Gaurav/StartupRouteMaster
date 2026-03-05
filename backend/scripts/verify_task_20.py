import httpx
import asyncio
import time
from datetime import datetime

async def verify():
    print("--- 📱 Task 20: Auto-Screen Dimming Verification ---")
    
    url_base = "http://localhost:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS
        res = await client.post(f"{url_base}/", json={"lat": 28.6139, "lng": 77.2090, "name": "Dimming Test"})
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Test Low Battery Dimming
        print("\n[Test 1] Sending 10% battery update...")
        res_low = await client.post(f"{url_base}/{event_id}/battery", json={
            "battery_level": 0.10, "lat": 28.6139, "lng": 77.2090
        })
        data_low = res_low.json()
        print(f"Auto-Dim Screen: {data_low.get('auto_dim_screen')}")
        
        # 3. Test Night-time Dimming (if it's night)
        now = datetime.utcnow()
        is_night = now.hour >= 23 or now.hour <= 4
        print(f"\n[Test 2] System Time: {now.hour}h (Is Night: {is_night})")
        
        if data_low.get("auto_dim_screen") == True:
            print("\n🏆 TASK 20 VERIFIED: UI hints correctly suggest power-saving dimming.")
        else:
            # If it's day AND battery was > 15%, it would be False. 
            # But here we sent 10%, so it should be True.
            print("\n❌ TASK 20 FAILED: Auto-dimming hint not triggered for 10% battery.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
