import httpx
import asyncio
import time

async def verify():
    print("--- 🛑 Task 45: SOS Auto-Cancellation via 'Safe-Word' Verification ---")
    
    url_sos = "http://127.0.0.1:8000/api/sos/"
    url_voice = "http://127.0.0.1:8000/api/voice/voice-trigger-sos"
    phone = "+91-7777777777"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger Initial SOS
        print("\n[Step 1] Triggering initial SOS...")
        res_init = await client.post(url_sos, json={"lat": 28.6, "lng": 77.2, "name": "Safe User", "phone": phone})
        event_id = res_init.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Speak Safe-Word via Voice API
        print("\n[Step 2] Sending voice safe-word: 'Everything is ALRIGHT'...")
        voice_payload = {
            "user_id": "user-abc",
            "transcript": "Everything is ALRIGHT now",
            "lat": 28.6, "lng": 77.2,
            "phone": phone,
            "trigger_method": "manual"
        }
        res_voice = await client.post(url_voice, json=voice_payload)
        # Voice returns TwiML if cancelled
        print(f"Voice Response: {res_voice.text[:50]}...")
        
        # 3. Verify Status is Resolved
        print("\n[Step 3] Verifying incident status...")
        res_get = await client.get(f"{url_sos}{event_id}")
        event = res_get.json()
        print(f"Status: {event.get('status')}")
        print(f"Extra Notes: {event.get('extra')}")
        
        if event.get("status") == "resolved" and "SAFE-WORD" in event.get("extra", ""):
            print("\n🏆 TASK 45 VERIFIED: SOS successfully auto-cancelled via safe-word.")
        else:
            print("\n❌ TASK 45 FAILED: Safe-word did not resolve the incident.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
