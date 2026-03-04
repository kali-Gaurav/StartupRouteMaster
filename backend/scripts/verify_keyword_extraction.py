import httpx
import asyncio
import json

async def test_keyword_extraction():
    url_base = "http://localhost:8000/api"
    print("--- 🔍 Keyword Extraction Verification ---")
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Trigger SOS
            res_sos = await client.post(f"{url_base}/sos/", json={"lat": 0, "lng": 0})
            event_id = res_sos.json()["id"]
            print(f"Event ID: {event_id}")

            # 2. Complex Transcript
            transcript = "I am in coach S4 seat 22 and I have chest pain"
            print(f"Transcript: {transcript}")
            await client.post(f"{url_base}/voice/triage-results?event_id={event_id}", 
                             data={"SpeechResult": transcript})
            
            # 3. Verify Structured Data
            res_all = await client.get(f"{url_base}/sos/all")
            event = next((e for e in res_all.json() if e["id"] == event_id), None)
            
            if event and "structured_info" in event:
                info = event["structured_info"]
                print(f"Extracted Info: {info}")
                print(f"Final Priority: {event['priority']}")
                
                success = (info.get("coach") == "S4" and 
                          info.get("seat") == "22" and 
                          any(kw in str(info.get("medical")) for kw in ["pain", "chest"]) and 
                          event['priority'] == 'critical')
                
                if success:
                    print("\n🏆 KEYWORD EXTRACTION VERIFIED: Structured data accurately extracted and prioritized.")
                else:
                    print("\n❌ FAIL: Data mismatch in extraction.")
            else:
                print("\n❌ FAIL: structured_info missing from event.")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_keyword_extraction())
