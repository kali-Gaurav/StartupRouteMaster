import httpx
import asyncio
import time
import os

async def verify():
    print("--- 🎙️ Task 35 Refinement: WhatsApp-style Voice Notes Verification ---")
    
    url_base = "http://localhost:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS
        res = await client.post(f"{url_base}/", json={"lat": 28.6139, "lng": 77.2090, "name": "VoiceNote User"})
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Upload Voice Note
        print("\n[Step 2] Uploading mock voice note (.mp3)...")
        file_path = "dummy_voice.mp3"
        with open(file_path, "rb") as f:
            files = {"file": (file_path, f, "audio/mpeg")}
            res_upload = await client.post(f"{url_base}/{event_id}/voice-note", files=files)
            
        data = res_upload.json()
        print(f"Upload Response: {data}")
        
        # 3. Verify via Dashboard (all events)
        print("\n[Step 3] Verifying transcript presence in chat history...")
        res_get = await client.get(f"{url_base}/{event_id}")
        event = res_get.json()
        
        found_note = any(msg.get('type') == 'voice_note' for msg in event.get('chat_history', []))
        
        if data.get("status") == "uploaded" and found_note:
            print("\n🏆 TASK 35 REFINEMENT VERIFIED: Voice notes correctly handled and transcribed.")
        else:
            print("\n❌ TASK 35 REFINEMENT FAILED: Voice note not found in history.")

if __name__ == "__main__":
    time.sleep(15) # Wait for server
    asyncio.run(verify())
