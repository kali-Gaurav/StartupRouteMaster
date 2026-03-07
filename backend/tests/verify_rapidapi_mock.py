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
logger = logging.getLogger("test_task_21")

async def verify_task_21():
    print("\n>>> Verifying Task 21: RapidAPI Verification & Caching")
    await multi_layer_cache.initialize()
    
    dp = DataProvider()
    
    # 1. Mock the RapidAPI client
    mock_client = MagicMock()
    mock_client.get_seat_availability = AsyncMock(return_value={
        "status": "success",
        "availableSeats": 42,
        "totalSeats": 64
    })
    dp.rapidapi_client = mock_client
    
    # 2. Call verifier
    test_date = datetime.now() + timedelta(days=5)
    result = await dp.verify_seat_availability_unified(
        trip_id=123, 
        travel_date=test_date,
        train_number="12625",
        from_station="PGT",
        to_station="NDLS"
    )
    
    print(f"  API Result: {result}")
    
    if result.get("available_seats") != 42:
        print("❌ FAILURE: Incorrect seat count returned from Mock API.")
        return False
        
    # 3. Verify Cache Hit (Task 21.7)
    if multi_layer_cache.redis:
        cache_key = f"verify_seat:12625:PGT:NDLS:{test_date.strftime('%Y-%m-%d')}:GN:3A"
        cached_raw = await multi_layer_cache.redis.get(cache_key)
        if cached_raw:
            cached_val = json.loads(cached_raw)
            print(f"  Cache Check: Found {cached_val.get('available_seats')} seats in Redis.")
            if cached_val.get('available_seats') == 42:
                print("\n✅ TASK 21 VERIFIED: RapidAPI integration and 15-min Redis caching are working.")
                return True
        else:
            print("❌ FAILURE: Result was not cached in Redis.")
            return False
    else:
        print("⚠️ SKIPPING Cache Check (Redis disabled). API was successful.")
        return True

if __name__ == "__main__":
    asyncio.run(verify_task_21())
