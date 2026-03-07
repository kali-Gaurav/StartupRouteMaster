import asyncio
import os
import sys
import logging
from unittest.mock import MagicMock, AsyncMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.route_engine.data_provider import DataProvider
from utils.external_api_health import api_health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_task_25")

async def verify_task_25():
    print("\n>>> Verifying Task 25: Fallback Synchronization & Circuit Breaker")
    
    dp = DataProvider()
    
    # 1. Mock RapidAPI to FAIL consistently
    mock_client = MagicMock()
    mock_client.get_seat_availability = AsyncMock(return_value={"status": "error", "message": "API Down"})
    dp.rapidapi_client = mock_client
    
    # 2. Trigger failures to trip the circuit breaker (Window size is 20, threshold 0.5)
    print("  Simulating 25 API failures...")
    for _ in range(25):
        await dp.verify_seat_availability_unified(1, datetime.now(), train_number="12625", from_station="PGT", to_station="KOTA")
    
    status = api_health.get_status()
    print(f"  Circuit Status: {status}")
    
    if not status["is_disabled"]:
        print("❌ FAILURE: Circuit breaker did not trip as expected.")
        return False
    
    # 3. Verify Fallback Source
    print("  Verifying source attribution during outage...")
    res = await dp.verify_seat_availability_unified(1, datetime.now(), train_number="12625", from_station="PGT", to_station="KOTA")
    
    print(f"  Result Source: {res.get('source')}")
    
    if res.get("source") != "database_fallback":
        print(f"❌ FAILURE: Expected source 'database_fallback', got '{res.get('source')}'")
        return False

    print("\n✅ TASK 25 VERIFIED: Circuit breaker and Database Fallback are robust.")
    return True

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(verify_task_25())
