import httpx
import asyncio
import time

async def verify():
    print("--- 🎙️ Task 21: Background Audio Buffer Verification ---")
    
    url_base = "http://localhost:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS with Pre-Trigger Context
        print("\n[Step 1] Triggering SOS with 30s 'flashback' audio transcript...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Retrospective Context User",
            "pre_trigger_transcript": "Hey you! Stop right there. Give me your bag now!"
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        print(f"Priority: {data.get('priority')}")
        print(f"Notes: {data.get('extra')}")
        
        if "[PRE-SOS CONTEXT]" in data.get("extra", ""):
            print("\n🏆 TASK 21 VERIFIED: Pre-trigger transcript correctly prepended to context.")
        else:
            print("\n❌ TASK 21 FAILED: Pre-trigger context was lost.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
