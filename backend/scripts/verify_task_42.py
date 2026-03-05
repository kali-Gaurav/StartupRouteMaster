import asyncio
import sys
import os
import shutil
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.sos import _save_event, _load_event, MEDIA_DIR
from services.emergency.escalation_service import escalation_service

async def verify():
    print("--- ♻️ Task 42: Automated Data Retention & Pruning Verification ---")
    
    event_id = "retention-test-42"
    # 1. Create an incident 31 days ago (Should trigger Hard-Delete)
    triggered_at = (datetime.utcnow() - timedelta(days=31)).isoformat()
    
    event = {
        "id": event_id,
        "status": "resolved",
        "triggered_at": triggered_at,
        "name": "Old Incident",
        "trip": {"pnr_number": "OLD-PNR-123"}
    }
    _save_event(event)
    
    # Create mock media folder
    media_path = os.path.join(MEDIA_DIR, event_id)
    os.makedirs(media_path, exist_ok=True)
    with open(os.path.join(media_path, "mock_audio.mp3"), "w") as f:
        f.write("mock data")
        
    print(f"Created 31-day old incident and media folder.")
    
    # 2. Run pruning
    print("\n[Step 2] Running hard-delete pruning cycle...")
    await escalation_service.purge_old_incidents()
    
    # 3. Check Result
    res = _load_event(event_id)
    media_exists = os.path.exists(media_path)
    
    print(f"Incident exists in memory: {res is not None}")
    print(f"Media folder exists: {media_exists}")
    
    if res is None and not media_exists:
        print("\n🏆 TASK 42 VERIFIED: Old data decisively wiped after 30 days.")
    else:
        print("\n❌ TASK 42 FAILED: Retention logic failed to purge data.")

if __name__ == "__main__":
    asyncio.run(verify())
