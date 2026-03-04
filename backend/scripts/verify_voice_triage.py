import httpx
import asyncio
import json

async def test_voice_triage():
    url_base = "http://localhost:8000/api"
    print("--- 🎙️ AI Voice Triage Verification ---")
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Trigger SOS
            print("\n[Step 1] Triggering Initial SOS...")
            payload = {
                "lat": 28.6428, "lng": 77.2190,
                "name": "Voice Test User", "phone": "+919876543210"
            }
            res_sos = await client.post(f"{url_base}/sos/", json=payload)
            event_id = res_sos.json()["id"]
            print(f"Event ID: {event_id}")

            # 2. Simulate Voice Results Webhook
            print(f"\n[Step 2] Simulating Voice Transcript: 'someone tried to snatch my bag'...")
            webhook_data = {
                "SpeechResult": "someone tried to snatch my bag"
            }
            # Note: We send as Form data, but event_id as Query Param
            res_voice = await client.post(f"{url_base}/voice/triage-results?event_id={event_id}", data=webhook_data)
            
            # 3. Verify Final SOS State
            print(f"\n[Step 3] Verifying SOS update...")
            # Using the /all endpoint to check the latest state
            res_all = await client.get(f"{url_base}/sos/all")
            events = res_all.json()
            updated_event = next((e for e in events if e["id"] == event_id), None)
            
            if updated_event:
                print(f"Status: {updated_event['status']}")
                print(f"Category: {updated_event.get('category')}")
                print(f"Priority: {updated_event.get('priority')}")
                
                if updated_event.get("category") == "security" and updated_event.get("priority") == "critical":
                    print("\n🏆 VOICE TRIAGE VERIFIED: Transcript successfully analyzed and event updated.")
                else:
                    print("\n❌ VERIFICATION FAILED: Event not correctly updated.")
            else:
                print("\n❌ FAILED: Could not find event after update.")

        except Exception as e:
            print(f"Error: {e}")
            print("Note: Ensure the backend server is running on port 8000.")

if __name__ == "__main__":
    asyncio.run(test_voice_triage())
