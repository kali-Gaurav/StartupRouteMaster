import asyncio
import sys
import os
import json
import uuid
from datetime import datetime, timedelta
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.session import SessionTransit
from services.emergency.safety_service import safety_service
from services.multi_layer_cache import multi_layer_cache

async def test_stationary_sos():
    db_transit = SessionTransit()
    user_id = f"test-safety-{uuid.uuid4().hex[:8]}"
    
    print("--- Automated SOS Trigger Verification ---")
    
    try:
        # 1. Setup Mock Risk Zone
        # Coordinates in a remote area (e.g., near a forest)
        risk_lat, risk_lon = 25.0, 75.0
        db_transit.execute(text("DELETE FROM risk_zones WHERE description = 'TEST_ZONE'"))
        db_transit.execute(text("""
            INSERT INTO risk_zones (id, latitude, longitude, risk_level, description)
            VALUES (:id, :lat, :lon, 4, 'TEST_ZONE')
        """), {"id": str(uuid.uuid4()), "lat": risk_lat, "lon": risk_lon})
        db_transit.commit()

        # 2. Simulate First Location Update (T=0)
        print("\n[Test 1] Initial location update (T=0)...")
        await safety_service.check_stationary_alert(user_id, risk_lat, risk_lon)
        
        # 3. Simulate Stationary for 31 Minutes (T=31)
        # Manually manipulate Redis timestamp to simulate time passing
        await multi_layer_cache.initialize()
        key = f"safety:user:{user_id}:pos"
        raw = await multi_layer_cache.redis.get(key)
        data = json.loads(raw)
        data['ts'] -= (31 * 60) # Push back timestamp by 31 mins
        await multi_layer_cache.redis.set(key, json.dumps(data))
        
        print("[Test 2] Checking stationary alert after 31 mins in risk zone...")
        res = await safety_service.check_stationary_alert(user_id, risk_lat, risk_lon)
        print(f"Result: {res['status']}")
        if res['status'] == 'trigger_sos_countdown':
            print(f"[PASS] SOS triggered correctly. Reason: {res['reason']}")
        else:
            print(f"[FAIL] SOS not triggered. Status: {res['status']}")

        # 4. Test Hub Exemption (NDLS)
        print("\n[Test 3] Checking stationary at NDLS (Hub Exemption)...")
        # NDLS approx 28.64, 77.21
        ndls_lat, ndls_lon = 28.6428, 77.2190
        await safety_service.check_stationary_alert(user_id, ndls_lat, ndls_lon)
        
        # Simulate 31 mins passing
        raw = await multi_layer_cache.redis.get(key)
        data = json.loads(raw)
        data['ts'] -= (31 * 60)
        await multi_layer_cache.redis.set(key, json.dumps(data))
        
        res_hub = await safety_service.check_stationary_alert(user_id, ndls_lat, ndls_lon)
        print(f"Result: {res_hub['status']}")
        if res_hub['status'] == 'stationary_at_hub':
            print(f"[PASS] Hub exemption worked for {res_hub.get('hub_name')}")
        else:
            print(f"[FAIL] Hub exemption failed. Status: {res_hub['status']}")

    finally:
        db_transit.execute(text("DELETE FROM risk_zones WHERE description = 'TEST_ZONE'"))
        db_transit.commit()
        db_transit.close()
        if multi_layer_cache.redis:
            await multi_layer_cache.redis.delete(f"safety:user:{user_id}:pos")

if __name__ == "__main__":
    asyncio.run(test_stationary_sos())
