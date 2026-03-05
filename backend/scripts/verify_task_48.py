import httpx
import asyncio
import time

async def verify():
    print("--- 📝 Task 48: Dynamic SOS Form Autofill Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS with details in transcript
        print("\n[Step 1] Triggering SOS with specific details in transcript...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Autofill User",
            "extra": "I am in coach S4 seat 25 and my chest has pain"
        }
        res = await client.post(f"{url_base}/", json=payload)
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Query Autofill
        print("\n[Step 2] Querying autofill suggestions...")
        res_af = await client.get(f"{url_base}/{event_id}/autofill")
        data = res_af.json()
        print(f"Suggestions: {data}")
        
        # 3. Check for extracted entities
        success = (
            data.get("coach_id") == "S4" and
            data.get("seat_number") == "25" and
            "pain" in data.get("medical_symptoms", [])
        )
        
        if success:
            print("\n🏆 TASK 48 VERIFIED: AI correctly suggested form values from transcript.")
        else:
            print("\n❌ TASK 48 FAILED: Autofill missed some entities.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
