import httpx
import asyncio
import time

async def verify():
    print("--- 🎙️ Task 22: Voice Wake-Word On-Device Engine Verification ---")
    
    url = "http://localhost:8000/api/voice/voice-trigger-sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Test Wake-Word Trigger (Low confidence transcript but high confidence method)
        print("\n[Step 1] Sending trigger with 'wake_word' method but gibberish transcript...")
        payload = {
            "user_id": "user-ww-1",
            "transcript": "something noisy and unclear",
            "lat": 28.6139, "lng": 77.2090,
            "trigger_method": "wake_word" # This should override transcript matching
        }
        res = await client.post(url, json=payload)
        data = res.json()
        print(f"Response: {data}")
        
        if data.get("status") == "triggered":
            print("\n🏆 TASK 22 VERIFIED: On-device wake-word signal correctly prioritized.")
        else:
            print("\n❌ TASK 22 FAILED: Wake-word signal was ignored.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
