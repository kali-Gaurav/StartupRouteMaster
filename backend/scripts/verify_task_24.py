import httpx
import asyncio
import time

async def verify():
    print("--- 🧠 Task 24: Emotional Stress Scoring (Audio Signals) Verification ---")
    
    url_base = "http://localhost:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS with High Pitch / Energy
        print("\n[Step 1] Triggering SOS with 300Hz pitch and 0.9 energy (Screaming simulation)...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Stress User",
            "extra": "Help", # Short text, but high stress audio
            "audio_pitch_hz": 300.0,
            "audio_energy": 0.9
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        print(f"Panic Score: {data.get('panic_score')}")
        print(f"Priority: {data.get('priority')}")
        
        # Base panic score for 'help' is high, plus 2 for pitch + 2 for energy
        if data.get("panic_score", 0) >= 8 and data.get("priority") == "critical":
            print("\n🏆 TASK 24 VERIFIED: Audio signals correctly boosted the panic score and priority.")
        else:
            print("\n❌ TASK 24 FAILED: Audio signals were ignored or score calculation is wrong.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
