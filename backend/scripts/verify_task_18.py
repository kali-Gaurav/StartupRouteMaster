import httpx
import asyncio
import time

async def verify():
    print("--- 🎙️ Task 18: Ambient Noise (VAD) Suppression Verification ---")
    
    url = "http://localhost:8000/api/voice/voice-trigger-sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Test High Noise Environment
        print("\n[Step 1] Sending trigger word in 85dB noise (Train Tunnel simulation)...")
        payload = {
            "user_id": "user-noisy-1",
            "transcript": "Help Help, something is wrong!",
            "lat": 28.6139, "lng": 77.2090,
            "noise_level_db": 85.0 # High noise
        }
        res = await client.post(url, json=payload)
        data = res.json()
        print(f"Response: {data}")
        
        if data.get("status") == "triggered" and data.get("vad_context") == "noisy_environment":
            print("\n🏆 TASK 18 VERIFIED: VAD correctly identified noisy environment.")
        else:
            print("\n❌ TASK 18 FAILED: Noise context not captured.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
