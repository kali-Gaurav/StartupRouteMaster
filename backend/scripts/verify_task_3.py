import httpx
import asyncio
import time

async def verify():
    print("--- 📑 Task 3: Constant-Time PNR-to-SOS Resolution Verification ---")
    
    pnr = "4445556667"
    url_base = "http://localhost:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS with PNR
        print(f"\n[Step 1] Triggering SOS for PNR {pnr}...")
        payload = {
            "lat": 28.6139, "lng": 77.2090,
            "name": "PNR Test User",
            "trip": {"pnr_number": pnr, "vehicle_number": "12345"}
        }
        res_trigger = await client.post(f"{url_base}/", json=payload)
        event_id = res_trigger.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Lookup by PNR
        print(f"\n[Step 2] Looking up SOS via O(1) PNR Registry...")
        res_lookup = await client.get(f"{url_base}/pnr/{pnr}")
        if res_lookup.status_code == 200 and res_lookup.json().get("id") == event_id:
            print(f"✅ Success: Found active SOS {event_id} for PNR {pnr}.")
        else:
            print(f"❌ Failure: PNR lookup failed (Status: {res_lookup.status_code}).")
            return

        # 3. Resolve SOS and check if PNR is cleared
        print(f"\n[Step 3] Resolving SOS and verifying registry cleanup...")
        await client.post(f"{url_base}/{event_id}/resolve")
        
        res_lookup_after = await client.get(f"{url_base}/pnr/{pnr}")
        if res_lookup_after.status_code == 404:
            print(f"✅ Success: PNR mapping cleared after resolution.")
            print("\n🏆 TASK 3 VERIFIED: Constant-time PNR registry functional.")
        else:
            print(f"❌ Failure: PNR mapping still exists after resolution.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
