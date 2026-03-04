import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.safety_service import safety_service

async def test_dead_zone():
    print("--- Dead Zone Prediction Verification ---")
    
    # 1. Test approaching a zone
    # Mock Zone is at (19.7, 73.4)
    # Simulate user at (19.6, 73.3) approx 15km away
    user_lat, user_lon = 19.6, 73.3
    
    print(f"\n[Test 1] User approaching Western Ghats (Current: {user_lat}, {user_lon})...")
    res = await safety_service.predict_dead_zone(user_lat, user_lon, speed_kmh=80.0)
    
    print(f"Result: {res['status']}")
    if res['status'] == 'upcoming_dead_zone':
        print(f"[PASS] Correctly predicted: {res['description']} in {res['eta_mins']} mins.")
    else:
        print(f"[FAIL] Failed to predict dead zone. Result: {res}")

    # 2. Test clear area
    print("\n[Test 2] User in clear area (Delhi: 28.6, 77.2)...")
    res_clear = await safety_service.predict_dead_zone(28.6, 77.2)
    print(f"Result: {res_clear['status']}")
    if res_clear['status'] == 'clear':
        print("[PASS] Correctly identified clear signal area.")
    else:
        print("[FAIL] False positive detected.")

if __name__ == "__main__":
    asyncio.run(test_dead_zone())
