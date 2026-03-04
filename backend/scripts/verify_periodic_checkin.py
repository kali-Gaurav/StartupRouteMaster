import httpx
import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.tracking_links import tracking_link_gen

async def test_checkin_confirmation():
    url_base = "http://localhost:8000/api/sos"
    print("--- 🛡️ Passenger Safety Confirmation Verification ---")
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Trigger SOS
            res_sos = await client.post(f"{url_base}/", json={"lat": 0, "lng": 0, "name": "Checkin Test"})
            event_id = res_sos.json()["id"]
            print(f"Created Event ID: {event_id}")

            # 2. Generate Token
            token = tracking_link_gen.generate_token(event_id)
            print(f"Generated Safety Token: {token[:20]}...")

            # 3. Confirm Safe
            print(f"\n[Test] Calling /confirm-safe with token...")
            res_confirm = await client.post(f"{url_base}/confirm-safe", params={"token": token})
            
            print(f"Status: {res_confirm.status_code}")
            print(f"Message: {res_confirm.json().get('message')}")
            
            # 4. Verify Final State
            res_all = await client.get(f"{url_base}/all")
            all_events = res_all.json()
            # print(f"DEBUG: All events type: {type(all_events)}")
            
            event = next((e for e in all_events if e.get("id") == event_id), None)
            
            if event:
                print(f"Final Status in DB: {event.get('status')}")
                if event.get("status") == "resolved":
                    print("\n🏆 SAFETY CONFIRMATION VERIFIED: Passenger successfully resolved the incident via token.")
                else:
                    print(f"\n❌ FAIL: Incident not resolved. Status: {event.get('status')}")
            else:
                print(f"\n❌ FAIL: Incident {event_id} not found in /all results.")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_checkin_confirmation())
