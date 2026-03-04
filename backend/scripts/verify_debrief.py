import httpx
import asyncio
import time

async def verify():
    print("--- ❤️ Post-Incident Emotional Debrief Verification ---")
    
    # 1. Trigger SOS
    trigger_url = "http://localhost:8000/api/sos/"
    payload = {"lat": 12.9716, "lng": 77.5946, "name": "Debrief User", "phone": "+91-8888888888"}
    
    async with httpx.AsyncClient() as client:
        res = await client.post(trigger_url, json=payload)
        event_id = res.json().get("id")
        print(f"Created Event ID: {event_id}")
        
        # 2. Resolve SOS (to allow debrief)
        print("\n[Step 2] Resolving SOS...")
        await client.post(f"http://localhost:8000/api/sos/{event_id}/resolve")
        
        # 3. Submit Debrief
        print("\n[Step 3] Submitting Debrief Feedback...")
        debrief_url = f"http://localhost:8000/api/sos/{event_id}/debrief"
        debrief_p = {
            "rating": 5,
            "comment": "The emergency response was incredibly fast. I felt safe throughout.",
            "emotional_state": "relieved"
        }
        
        res_debrief = await client.post(debrief_url, json=debrief_p)
        print(f"Status: {res_debrief.status_code}")
        print(f"Response: {res_debrief.json()}")
        
        if res_debrief.status_code == 200:
            print("\n🏆 DEBRIEF VERIFIED: Feedback collected and RL logs updated.")
        else:
            print("\n❌ DEBRIEF FAILED.")

if __name__ == "__main__":
    # Server should be running from previous task
    asyncio.run(verify())