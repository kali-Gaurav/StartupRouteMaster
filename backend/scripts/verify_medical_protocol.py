import asyncio
import sys
import os
import sqlite3

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.alert_manager import EmergencyAlertManager
from database.session import SessionTransit

async def test_medical_protocol():
    print("--- 🚑 Medical Emergency Protocol Verification ---")
    
    # 1. Seed facility data for NDLS
    db_transit = SessionTransit()
    try:
        from database.models import Stop, StationFacilities
        ndls = db_transit.query(Stop).filter(Stop.code == 'NDLS').first()
        if ndls:
            # Ensure facilities exists and is correctly linked
            conn = db_transit.connection().connection
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO station_facilities (stop_id) VALUES (?)", (ndls.id,))
            c.execute("UPDATE station_facilities SET has_ambulance=1, medical_contact='+91-11-23340000', medical_rank=5 WHERE stop_id=?", (ndls.id,))
            conn.commit()
            print(f"Seeded NDLS (ID: {ndls.id}) with high-rank medical facilities.")
    finally:
        db_transit.close()

    manager = EmergencyAlertManager()
    
    # Simulate SOS with Medical context
    sos_event = {
        "id": "med-test-999",
        "lat": 28.6428,
        "lng": 77.2190,
        "extra": "Passenger having severe breathing issues.",
        "trip": {"vehicle_number": "12628", "coach": "B2"},
        "railway_context": {"next_station": "New Delhi"}, # Explicitly provide for dispatch test
        "chat_history": [{"role": "user", "content": "I can't breathe, help!"}]
    }
    
    print("\n[Test] Processing Medical SOS near NDLS...")
    res = await manager.process_sos_alert(sos_event)
    
    dispatch = res.get("dispatch", {})
    details = dispatch.get("medical_details", {})
    
    print(f"Threat Category: {res.get('category')}")
    print(f"Target Station: {details.get('target_station')}")
    print(f"Ambulance Ready: {details.get('ambulance_available')}")
    print(f"Contact: {details.get('medical_contact')}")
    print(f"Dispatch Status: {dispatch.get('status')}")
    
    if res.get('category') == 'medical' and details.get('ambulance_available') == 'YES':
        print("\n🏆 MEDICAL PROTOCOL VERIFIED: High-rank facilities identified and dispatched.")
    else:
        print("\n❌ VERIFICATION FAILED: Medical details mismatch.")

if __name__ == "__main__":
    asyncio.run(test_medical_protocol())
