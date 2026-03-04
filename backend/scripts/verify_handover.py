import httpx
import asyncio
import json

async def test_human_handover():
    url_base = "http://localhost:8000/api/sos"
    print("--- 👤 Human Handover Protocol Verification ---")
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Trigger SOS
            res_sos = await client.post(f"{url_base}/", json={"lat": 0, "lng": 0, "name": "Handover Test"})
            event_id = res_sos.json()["id"]
            print(f"Created Event ID: {event_id}")

            # 2. Claim SOS (Human Takeover)
            print(f"\n[Test] Calling /claim for incident {event_id}...")
            res_claim = await client.post(f"{url_base}/{event_id}/claim")
            
            print(f"Status: {res_claim.status_code}")
            data = res_claim.json()
            
            # Note: We need to check the raw storage or rely on the response
            # Since SOSEventResponse doesn't have ai_automation_enabled, we check the 'extra' field
            
            is_claimed = data.get("status") == "responding"
            has_audit = "HANDED OVER TO HUMAN ADMIN" in data.get("extra", "")
            
            if is_claimed and has_audit:
                print("\n🏆 HUMAN HANDOVER VERIFIED: Incident successfully claimed and audit trail updated.")
            else:
                print(f"\n❌ FAIL: Claim logic unsuccessful. Data: {data}")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_human_handover())
