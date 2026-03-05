import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.sos import _save_event, _load_event
from services.emergency.escalation_service import escalation_service

async def verify():
    print("--- 🛡️ Task 41: Automated GDPR/DPDP Data Redaction Verification ---")
    
    event_id = "privacy-test-41"
    # 1. Create an incident 25 hours ago (Should trigger Soft-Scrub)
    triggered_at = (datetime.utcnow() - timedelta(hours=25)).isoformat()
    
    event = {
        "id": event_id,
        "status": "resolved",
        "triggered_at": triggered_at,
        "name": "Sensitive Passenger",
        "phone": "+91-9999999999",
        "extra": "Very sensitive data",
        "chat_history": [{"sender": "user", "content": "I am in danger"}],
        "location_history": [{"lat": 28.6, "lng": 77.2, "ts": triggered_at}]
    }
    _save_event(event)
    print(f"Created sensitive event 25 hours ago.")
    
    # 2. Run pruning
    print("\n[Step 2] Running privacy pruning cycle...")
    await escalation_service.purge_old_incidents()
    
    # 3. Check Result
    res = _load_event(event_id)
    print(f"Final Name: {res.get('name')}")
    print(f"Final Extra: {res.get('extra')}")
    print(f"Privacy Status: {res.get('privacy_status')}")
    
    if res.get("name") == "ANONYMOUS_USER" and res.get("privacy_status") == "scrubbed":
        print("\n🏆 TASK 41 VERIFIED: PII successfully redacted for 24h+ incidents.")
    else:
        print("\n❌ TASK 41 FAILED: PII was not scrubbed.")

if __name__ == "__main__":
    asyncio.run(verify())
