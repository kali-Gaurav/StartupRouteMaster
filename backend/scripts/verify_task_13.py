import httpx
import asyncio
import time

async def verify():
    print("--- 🚆 Task 13: Dynamic Ping Frequency Verification ---")
    
    url_base = "http://localhost:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS with Station context (SBC)
        # Assuming our mock AlertManager detects station context and sets speed low
        print("\n[Step 1] Triggering SOS near a station (SBC)...")
        payload = {
            "lat": 12.9781, "lng": 77.5697, # Bangalore SBC coords
            "name": "Speed Test User",
            "trip": {"vehicle_number": "12627"} # Karnataka Exp
        }
        res = await client.post(f"{url_base}/", json=payload)
        data = res.json()
        
        # Note: If trigger_sos itself calculates speed, it will be in the response
        ping = data.get("ping_interval_ms")
        print(f"Response Ping Interval: {ping} ms")
        
        if ping == 120000:
            print("\n🏆 TASK 13 VERIFIED: Ping frequency throttled for stationary/slow train.")
        elif ping == 30000:
            print("\n⚠️ Note: Default medium ping detected. Checking if station context was picked up...")
            # We'll check the railway_context
            if data.get('railway_context', {}).get('current_station'):
                 print("   Station context was found. Throttling should have triggered.")
            else:
                 print("   Station context not found in DB. Test might need deeper seeding.")
        else:
            print(f"\n❌ TASK 13 FAILED: Unexpected ping interval {ping}.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
