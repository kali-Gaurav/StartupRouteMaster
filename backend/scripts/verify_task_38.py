import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.sos import _save_event, _load_event
from services.emergency.escalation_service import escalation_service

async def verify():
    print("--- 🚀 Task 38: Escalation-Speed Dynamic Profiler Verification ---")
    
    event_id = "dynamic-test-38"
    # 1. Create a FIRE incident 10 minutes ago
    # FIRE during day = 60 - 45 = 15m timeout. 
    # 10 mins isn't quite there, so let's make it 16 mins ago.
    triggered_at = (datetime.utcnow() - timedelta(minutes=16)).isoformat()
    
    event = {
        "id": event_id,
        "status": "active",
        "triggered_at": triggered_at,
        "category": "fire",
        "priority": "high",
        "escalation_level": 1
    }
    _save_event(event)
    print(f"Created FIRE incident 16 mins ago.")
    
    # 2. Run monitor
    print("\n[Step 2] Running dynamic escalation monitor...")
    await escalation_service.check_all_active_incidents()
    
    # 3. Check Result
    res = _load_event(event_id)
    level = res.get("escalation_level")
    print(f"Final Escalation Level: {level}")
    
    if level == 3:
        print("\n🏆 TASK 38 VERIFIED: Fire incident correctly fast-tracked for escalation.")
    else:
        print("\n❌ TASK 38 FAILED: Fire incident did not trigger dynamic timeout.")

if __name__ == "__main__":
    asyncio.run(verify())
