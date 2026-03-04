import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.sos import _save_event, _load_event, get_all_sos
from services.emergency.escalation_service import escalation_service

async def verify():
    print("--- ♻️ Data Retention: 30-Day Auto-Purge Verification ---")
    
    event_id = "purge-test-99"
    # Create an event 35 days old
    triggered_at = (datetime.utcnow() - timedelta(days=35)).isoformat()
    
    old_event = {
        "id": event_id,
        "status": "resolved",
        "triggered_at": triggered_at,
        "name": "Ancient Incident"
    }
    
    _save_event(old_event)
    print(f"Created ancient event {event_id} (Age: 35 days)")
    
    # Verify it exists
    all_ev = await get_all_sos()
    if any(e['id'] == event_id for e in all_ev):
        print("Confirmed: Ancient event is in storage.")
    
    # Run Purge
    print("\n[Step 2] Running data retention purge...")
    await escalation_service.purge_old_incidents(days=30)
    
    # Verify it's gone
    all_ev_after = await get_all_sos()
    if not any(e['id'] == event_id for e in all_ev_after):
        print("\n🏆 AUTO-PURGE VERIFIED: 35-day old incident was deleted.")
    else:
        print("\n❌ AUTO-PURGE FAILED: Ancient incident still exists.")

if __name__ == "__main__":
    asyncio.run(verify())