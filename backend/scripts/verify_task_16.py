import httpx
import asyncio
import time

async def verify():
    print("--- 💀 Task 16: Battery-Critical Last Breath Verification ---")
    
    url_base = "http://localhost:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS
        res = await client.post(f"{url_base}/", json={"lat": 28.6139, "lng": 77.2090, "name": "LastBreath Test"})
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Send Last Breath Update
        print("\n[Step 2] Sending 'is_last_breath' priority payload...")
        res_dead = await client.post(f"{url_base}/{event_id}/battery", json={
            "battery_level": 0.01,
            "lat": 28.6139,
            "lng": 77.2090,
            "is_last_breath": True
        })
        
        data = res_dead.json()
        print(f"Response: {data}")
        
        if data.get("status") == "last_breath_acknowledged":
            print("\n🏆 TASK 16 VERIFIED: Hardware-priority 'Last Breath' sync functional.")
        else:
            print("\n❌ TASK 16 FAILED: Priority update not recognized correctly.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
