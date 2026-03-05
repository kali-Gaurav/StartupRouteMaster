import httpx
import asyncio
import time

async def verify():
    print("--- 🚉 Task 37: Geo-fenced Responder Auto-Dispatch Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Trigger SOS for a train approaching a station
        print("\n[Step 1] Triggering SOS for train approaching Bhopal Junction...")
        payload = {
            "lat": 23.2599, "lng": 77.4126, 
            "name": "Proactive User",
            "trip": {"vehicle_number": "12625"} # Kerala Express
        }
        
        # Note: LiveStatusService should return 'Bhopal Jn' as next_station for this train/location
        res = await client.post(f"{url_base}/", json=payload)
        data = res.json()
        
        notified = data.get("station_master_notified", False)
        extra = data.get("extra", "")
        
        print(f"Station Master Notified: {notified}")
        print(f"Notes: {extra}")
        
        if notified or "Station Master" in extra:
            print("\n🏆 TASK 37 VERIFIED: Proactive station-master dispatch logic triggered.")
        else:
            print("\n❌ TASK 37 FAILED: System did not notify the upcoming station master.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
