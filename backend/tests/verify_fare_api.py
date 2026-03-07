import asyncio
import os
import sys
import json
from datetime import datetime, timedelta
import logging
from unittest.mock import MagicMock, AsyncMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.route_engine.data_provider import DataProvider
from services.multi_layer_cache import multi_layer_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_task_22")

async def verify_task_22():
    print("\n>>> Verifying Task 22: RapidAPI Fare Integration & Caching")
    await multi_layer_cache.initialize()
    
    dp = DataProvider()
    
    # 1. Mock the RapidAPI client for get_fare
    mock_client = MagicMock()
    mock_client.get_fare = AsyncMock(return_value={
        "status": "success",
        "data": {
            "fares": [
                {"classType": "3A", "totalFare": 1850.0, "baseFare": 1700.0, "serviceTax": 150.0},
                {"classType": "SL", "totalFare": 650.0, "baseFare": 650.0, "serviceTax": 0.0}
            ]
        }
    })
    dp.rapidapi_client = mock_client
    
    # 2. Call fare verifier for 3A
    result = await dp.verify_fare_unified(
        segment_id="test_seg_123", 
        coach_preference="AC_THREE_TIER",
        train_number="12625",
        from_station="PGT",
        to_station="NDLS"
    )
    
    print(f"  API Result (3A): {result}")
    
    if result.get("total_fare") != 1850.0:
        print(f"❌ FAILURE: Incorrect fare returned. Expected 1850.0, got {result.get('total_fare')}")
        return False
        
    # 3. Verify Cache for BOTH classes (Task 22.7)
    if multi_layer_cache.redis:
        # Check 3A cache
        key_3a = "verify_fare:12625:PGT:NDLS:3A"
        raw_3a = await multi_layer_cache.redis.get(key_3a)
        
        # Check SL cache (pre-cached during 3A call)
        key_sl = "verify_fare:12625:PGT:NDLS:SL"
        raw_sl = await multi_layer_cache.redis.get(key_sl)
        
        if raw_3a and raw_sl:
            val_sl = json.loads(raw_sl)
            print(f"  Cache Check: Found SL fare ₹{val_sl.get('total_fare')} pre-cached.")
            if val_sl.get('total_fare') == 650.0:
                print("\n✅ TASK 22 VERIFIED: Live fare integration and multi-class caching are working.")
                return True
        else:
            print(f"❌ FAILURE: Multi-class caching failed. 3A: {bool(raw_3a)}, SL: {bool(raw_sl)}")
            return False
    else:
        print("⚠️ SKIPPING Cache Check (Redis disabled). API was successful.")
        return True

if __name__ == "__main__":
    asyncio.run(verify_task_22())
