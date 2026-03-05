import httpx
import asyncio
import time

async def verify():
    print("--- 🤝 Task 56: Multi-party Safety Handshake Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger Initial SOS
        print("\n[Step 1] Triggering initial SOS...")
        res_init = await client.post(f"{url_base}/", json={"lat": 28.6, "lng": 77.2, "name": "Handshake User"})
        event_id = res_init.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Perform Handshake: Victim
        print("\n[Step 2] Victim acknowledging...")
        await client.post(f"{url_base}/{event_id}/handshake", json={"party": "victim"})
        
        # 3. Perform Handshake: Responder
        print("\n[Step 3] Responder acknowledging...")
        await client.post(f"{url_base}/{event_id}/handshake", json={"party": "responder"})
        
        # 4. Perform Handshake: Admin (Completion)
        print("\n[Step 4] Admin acknowledging (Triggering completion)...")
        res_final = await client.post(f"{url_base}/{event_id}/handshake", json={"party": "admin"})
        data = res_final.json()
        print(f"Final Status: {data.get('current_status')}")
        
        # 5. Verify metadata flag
        print("\n[Step 5] Verifying incident completion flag...")
        res_get = await client.get(f"{url_base}/{event_id}")
        event = res_get.json()
        print(f"Extra Notes: {event.get('extra')}")
        
        if all(data.get("current_status", {}).values()) and "SAFE HANDSHAKE COMPLETE" in event.get("extra", ""):
            print("\n🏆 TASK 56 VERIFIED: Triple-confirmation handshake successful.")
        else:
            print("\n❌ TASK 56 FAILED: Handshake did not complete or flag missing.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
