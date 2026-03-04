import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.emergency.alert_manager import EmergencyAlertManager

async def verify():
    print("--- ⏱️ Dynamic ETA Calibration Verification ---")
    
    # Mock coordinates (e.g. New Delhi area)
    test_lat = 28.6139
    test_lng = 77.2090
    
    result = EmergencyAlertManager._find_nearest_authority(test_lat, test_lng, "security")
    
    if result:
        dist = result.get('distance_km', 0)
        eta = result.get('eta_mins', 0)
        
        print(f"Nearest Authority: {result.get('name')} ({result.get('type')})")
        print(f"Distance: {dist} km")
        print(f"Calculated Dynamic ETA: {eta} mins")
        
        # Verify the calculation (dist / 40 * 60 + DB_BASELINE)
        # We know New Delhi RPF Post has 2 mins in DB
        db_baseline = 2 
        expected_eta = round(db_baseline + (dist / 40.0) * 60)
        
        if eta == expected_eta:
            print("\n🏆 ETA CALIBRATION VERIFIED: Dynamic calculation is correct.")
        else:
            print(f"\n❌ ETA CALIBRATION FAILED: Expected {expected_eta}, got {eta}")
    else:
        print("❌ No authorities found to test. Ensure the database has seeded emergency authorities.")

if __name__ == "__main__":
    asyncio.run(verify())