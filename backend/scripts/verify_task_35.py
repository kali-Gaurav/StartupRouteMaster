import httpx
import asyncio
import time

async def verify():
    print("--- 🧠 Task 35: Multi-modal SOS (Weighted Intelligence) Verification ---")
    
    url_base = "http://localhost:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS with Multiple High-Risk Signals
        # Impact (+3), Pitch (+2), Medical Text (+5) = Score 10 (Critical)
        print("\n[Step 1] Triggering Multi-modal SOS (High-G + High Pitch + Medical Text)...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Fusion User",
            "extra": "Help I have sharp chest pain",
            "accel_g_force": 5.5, # > 4.0 threshold (+3)
            "audio_pitch_hz": 280.0, # > 250 threshold (+2)
            "audio_energy": 0.9, # (+2)
            "pre_trigger_transcript": "User heard screaming..." # (+2)
        }
        # Note: Logic also adds base scores from keywords.
        
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        score = data.get('panic_score')
        priority = data.get('priority')
        print(f"Final Panic Score: {score}")
        print(f"Priority Level: {priority}")
        
        if score == 10 and priority == "critical":
            print("\n🏆 TASK 35 VERIFIED: Multi-modal weighted intelligence correctly fused signals.")
        else:
            print("\n❌ TASK 35 FAILED: Intelligence fusion did not reach critical threshold.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
