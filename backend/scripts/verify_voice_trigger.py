import httpx
import asyncio
import time

async def verify():
    print("--- 🎙️ Multi-modal Voice Trigger Verification ---")
    
    url = "http://localhost:8000/api/voice/voice-trigger-sos"
    
    # 1. Test Ignored Phrase
    print("\n[Test 1] Sending non-triggering phrase...")
    payload1 = {
        "user_id": "user-123",
        "transcript": "I am feeling good today.",
        "lat": 28.6139,
        "lng": 77.2090
    }
    
    async with httpx.AsyncClient() as client:
        res1 = await client.post(url, json=payload1)
        print(f"Status: {res1.status_code}")
        print(f"Response: {res1.json()}")
        
    # 2. Test Trigger Phrase
    print("\n[Test 2] Sending panic phrase: 'Help Help, please save me!'")
    payload2 = {
        "user_id": "user-123",
        "transcript": "Help Help, please save me!",
        "lat": 28.6139,
        "lng": 77.2090,
        "phone": "+91-9999999999"
    }
    
    async with httpx.AsyncClient() as client:
        res2 = await client.post(url, json=payload2)
        print(f"Status: {res2.status_code}")
        resp2 = res2.json()
        print(f"Response: {resp2}")
        
        if resp2.get("status") == "triggered":
            print("\n🏆 VOICE TRIGGER VERIFIED: SOS initiated successfully.")
        else:
            print("\n❌ VOICE TRIGGER FAILED: Trigger word not recognized.")

if __name__ == "__main__":
    # Wait for server
    time.sleep(3)
    asyncio.run(verify())