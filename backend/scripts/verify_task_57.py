import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.sos import _save_event, _load_event
from services.emergency.escalation_service import escalation_service

async def verify():
    print("--- 🧠 Task 57: AI-Generated Incident Summary Verification ---")
    
    event_id = "ai-summary-test-57"
    # 1. Create an incident 61 mins ago
    triggered_at = (datetime.utcnow() - timedelta(minutes=61)).isoformat()
    
    event = {
        "id": event_id,
        "status": "active",
        "triggered_at": triggered_at,
        "category": "medical",
        "priority": "high",
        "name": "Summary User",
        "extra": "Help I have chest pain",
        "escalation_level": 1
    }
    _save_event(event)
    print(f"Created 61-min old medical incident.")
    
    # 2. Run escalation (Which should trigger AI Summary)
    print("\n[Step 2] Running escalation logic...")
    await escalation_service.check_all_active_incidents()
    
    # 3. Check Result
    res = _load_event(event_id)
    summary = res.get("hq_summary")
    extra = res.get("extra", "")
    
    print(f"Final Escalation Level: {res.get('escalation_level')}")
    print(f"AI Summary: {summary}")
    print(f"Notes tail: {extra[-50:]}")
    
    if summary and "[MEDICAL]" in summary and "AUTO-ESCALATED" in extra:
        print("\n🏆 TASK 57 VERIFIED: AI summary correctly generated and attached to escalation.")
    else:
        print("\n❌ TASK 57 FAILED: Summary missing or incorrect.")

if __name__ == "__main__":
    asyncio.run(verify())
