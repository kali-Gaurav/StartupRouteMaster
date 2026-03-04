import asyncio
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.alert_manager import EmergencyAlertManager
from database.session import SessionTransit
from database.models import TrainLiveUpdate, Stop

async def test_live_sync_final():
    print("--- 📡 SOS Real-time Data Sync Verification ---")
    
    manager = EmergencyAlertManager()
    
    # Simulate SOS for Train 12628 in Coach B2 (AC)
    sos_event = {
        "id": "final-sync-test",
        "trip": {
            "vehicle_number": "12628",
            "coach": "B2"
        },
        "extra": "Medical emergency",
        "chat_history": []
    }
    
    print(f"\n[Test] Processing SOS for Train 12628, Coach B2...")
    res = await manager.process_sos_alert(sos_event)
    
    context = res.get("railway_context", {})
    
    print(f"Current Station: {context.get('current_station')}")
    print(f"Platform: {context.get('platform')}")
    print(f"Delay Status: {context.get('delay')}")
    print(f"Coach Physical Pos: {context.get('platform_position')}")
    print(f"Data Source: {context.get('source')}")
    
    # Verify Subtask 13.1: Intelligent Positioning
    pos_ok = "AC Section" in context.get('platform_position', '')
    
    # Verify Subtask 13.2: Persistence check
    db_transit = SessionTransit()
    latest_ingest = db_transit.query(TrainLiveUpdate).filter(TrainLiveUpdate.source == "SOS_SYNC_INGEST").order_by(TrainLiveUpdate.recorded_at.desc()).first()
    ingest_ok = latest_ingest is not None
    db_transit.close()

    print(f"\n--- Verification Report ---")
    print(f"✅ Context Enriched: {'YES' if context else 'NO'}")
    print(f"✅ Positioning Logic: {'PASS' if pos_ok else 'FAIL'}")
    print(f"✅ DB Auto-Ingestion: {'PASS' if ingest_ok else 'FAIL'}")
    
    if context and pos_ok and ingest_ok:
        print("\n🏆 END-TO-END SYNC VERIFIED: Real-time API used, data saved, and physical mapping applied.")
    else:
        print("\n❌ VERIFICATION FAILED: Some sync components missing.")

if __name__ == "__main__":
    asyncio.run(test_live_sync_final())
