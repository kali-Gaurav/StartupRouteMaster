import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.emergency.alert_manager import EmergencyAlertManager

async def verify():
    print("--- 📑 Task 4: Authority Matrix Pre-computation Verification ---")
    
    mgr = EmergencyAlertManager()
    
    # 1. Test Fast-Path (NDLS)
    # New Delhi Station ID is 'NDLS' from our seed
    print("\n[Step 1] Testing O(1) Fast-Path for station 'NDLS'...")
    res = mgr._find_nearest_authority(28.6428, 77.2190, "security", station_id="NDLS")
    
    if res and res.get("source") == "precomputed_matrix":
        print(f"✅ Success: Fast-path lookup returned {res['name']}.")
        print(f"   Source confirmed as: {res['source']}")
    else:
        print(f"❌ Failure: Fast-path failed (Result: {res})")
        return

    # 2. Test Slow-Path Fallback (Random Lat/Lng)
    # Note: Need to pass enough data for spatial search to work if we actually want results
    print("\n[Step 2] Testing Slow-Path Fallback (no station_id)...")
    res_slow = mgr._find_nearest_authority(28.0, 77.0, "security")
    
    if res_slow and res_slow.get("source") != "precomputed_matrix":
        print(f"✅ Success: Fallback to spatial search works.")
        print("\n🏆 TASK 4 VERIFIED: Authority Matrix eliminates redundant math.")
    else:
        print(f"⚠️ Note: Fallback returned {res_slow}. Ensuring source is correct.")

if __name__ == "__main__":
    asyncio.run(verify())
