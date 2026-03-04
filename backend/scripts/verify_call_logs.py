import httpx
import asyncio
import json

async def test_call_logs():
    url_base = "http://localhost:8000/api"
    print("--- 📝 Persistent Call Logs Verification ---")
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Trigger SOS
            res_sos = await client.post(f"{url_base}/sos/", json={"lat": 0, "lng": 0})
            event_id = res_sos.json()["id"]
            print(f"Event ID: {event_id}")

            # 2. First Transcript
            await client.post(f"{url_base}/voice/triage-results?event_id={event_id}", 
                             data={"SpeechResult": "I am feeling sick"})
            
            # 3. Second Transcript
            await client.post(f"{url_base}/voice/triage-results?event_id={event_id}", 
                             data={"SpeechResult": "Send an ambulance please"})
            
            # 4. Verify Logs
            res_all = await client.get(f"{url_base}/sos/all")
            event = next((e for e in res_all.json() if e["id"] == event_id), None)
            
            if event and "call_logs" in event:
                logs = event["call_logs"]
                print(f"Total Call Logs: {len(logs)}")
                for log in logs:
                    print(f"  - [{log['timestamp']}] {log['content']}")
                
                if len(logs) == 2:
                    print("\n🏆 CALL LOGS VERIFIED: Multiple transcripts persisted correctly.")
                else:
                    print(f"\n❌ FAIL: Expected 2 logs, found {len(logs)}")
            else:
                print("\n❌ FAIL: call_logs missing from event.")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_call_logs())
