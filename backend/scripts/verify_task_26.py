import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.sos import _save_event, _load_event
from services.emergency.escalation_service import escalation_service

async def verify():
    print("--- 🌙 Task 26: Night-Bias Escalation Verification ---")
    
    event_id = "night-test-26"
    # 1. Create an incident 25 minutes ago
    # This should ONLY escalate if it's currently night (timeout=20)
    triggered_at = (datetime.utcnow() - timedelta(minutes=25)).isoformat()
    
    event = {
        "id": event_id,
        "status": "active",
        "triggered_at": triggered_at,
        "name": "Night Passenger",
        "escalation_level": 1
    }
    _save_event(event)
    print(f"Created event 25 mins ago: {triggered_at}")
    
    # 2. Run monitor
    print("\n[Step 2] Running escalation monitor...")
    await escalation_service.check_all_active_incidents()
    
    # 3. Check Result
    res = _load_event(event_id)
    level = res.get("escalation_level")
    
    now = datetime.utcnow()
    is_night = now.hour >= 23 or now.hour <= 4
    
    print(f"Current Hour: {now.hour} (Is Night: {is_night})")
    print(f"Final Escalation Level: {level}")
    
    if is_night and level == 3:
        print("\n🏆 TASK 26 VERIFIED: Fast-tracked nighttime escalation working.")
    elif not is_night and level == 1:
        print("\n🏆 TASK 26 VERIFIED: Normal daytime timeout maintained.")
    else:
        print("\n❌ TASK 26 FAILED: Escalation logic did not respect night-bias.")

if __name__ == "__main__":
    asyncio.run(verify())
