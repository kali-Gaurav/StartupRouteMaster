import httpx
import asyncio
import time

async def verify():
    print("--- 👨‍👩‍👧‍👦 Task 52: Dynamic Incident Redaction for Family View Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger Technical SOS
        print("\n[Step 1] Triggering technical SOS with raw panic data...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Victim Name",
            "extra": "I have severe heart pain help",
            "accel_g_force": 5.0
        }
        res = await client.post(f"{url_base}/", json=payload)
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Query Family View
        print("\n[Step 2] Querying family-redacted view...")
        res_fv = await client.get(f"{url_base}/{event_id}/family-view")
        data = res_fv.json()
        print(f"Family View Data: {data}")
        
        # 3. Verify Redaction
        # Technical fields like panic_score, audio_energy, chat_history SHOULD NOT exist
        is_redacted = (
            "panic_score" not in data and
            "chat_history" not in data and
            "status_display" in data
        )
        
        if is_redacted and data.get("status_display") == "Request received, locating help...":
            print("\n🏆 TASK 52 VERIFIED: Family view correctly redacted technical telemetry.")
        else:
            print("\n❌ TASK 52 FAILED: Technical data leaked to family view or status mapping failed.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
