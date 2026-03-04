import asyncio
import sys
import os
import uuid
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.sos import _save_event, _load_event
from services.emergency.escalation_service import escalation_service

async def verify():
    print("--- 🚨 Level 3 National HQ Escalation Verification ---")
    
    event_id = "escalation-test-77"
    triggered_at = (datetime.utcnow() - timedelta(minutes=65)).isoformat()
    
    # 1. Setup an "Old" Active Event (65 mins ago)
    old_event = {
        "id": event_id,
        "status": "active",
        "priority": "high",
        "triggered_at": triggered_at,
        "lat": 28.6139, "lng": 77.2090,
        "name": "Delayed Response Victim",
        "escalation_level": 1
    }
    
    _save_event(old_event)
    print(f"Created event {event_id} triggered at {triggered_at}")
    
    # 2. Run Escalation Check
    print("\n[Step 2] Running escalation monitor check...")
    await escalation_service.check_all_active_incidents()
    
    # 3. Verify Result
    updated_event = _load_event(event_id)
    print(f"Updated Escalation Level: {updated_event.get('escalation_level')}")
    print(f"Updated Priority: {updated_event.get('priority')}")
    
    if updated_event.get('escalation_level') == 3 and "hq_dispatch" in updated_event:
        print("\n🏆 HQ ESCALATION VERIFIED: Level 3 triggered successfully.")
    else:
        print("\n❌ HQ ESCALATION FAILED: Event not correctly escalated.")

if __name__ == "__main__":
    asyncio.run(verify())