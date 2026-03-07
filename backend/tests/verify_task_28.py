import asyncio
import os
import sys
import logging
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.data_structures import Route, RouteSegment
from services.search_service import SearchService
from database.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_task_28")

async def verify_task_28():
    print("\n>>> Verifying Task 28: Live Delay Adjustments (Rappid.in)")
    
    db = SessionLocal()
    service = SearchService(db)
    
    # 1. Mock RappidAPIClient to return a 30-minute delay
    mock_status = {
        "success": True,
        "data": [
            {"delay": "30 mins", "current_station": "NDLS", "platform": "4"}
        ]
    }
    # In search_service, we call data_provider.get_live_delay
    # data_provider.rappid_client is the AsyncRappidAPIClient
    service.data_provider.rappid_client = MagicMock()
    service.data_provider.rappid_client.fetch_train_status = AsyncMock(return_value=mock_status)
    
    # Mock other API dependencies to return instantly
    service.data_provider.rapidapi_client = MagicMock()
    service.data_provider.verify_seat_availability_unified = AsyncMock(return_value={"available_seats": 10})
    service.data_provider.verify_fare_unified = AsyncMock(return_value={"total_fare": 500.0})

    # 2. Create a route to verify
    r1 = Route(segments=[RouteSegment(
        trip_id=123, departure_stop_id=1, arrival_stop_id=2,
        departure_time=datetime.now(), arrival_time=datetime.now() + timedelta(hours=2),
        duration_minutes=120, distance_km=100.0,
        departure_code="S1", arrival_code="S2", train_number="12625"
    )])
    
    # 3. Call verification (which triggers get_live_delay)
    print("  Triggering parallel verification with 30-min delay mock...")
    verified = await service._verify_single_route(r1, datetime.now())
    
    print(f"  Total Delay in Metadata: {verified.metadata.get('total_delay_mins')} mins")
    
    # Check if arrival_time was shifted (Task 28.3)
    # Original duration was 120, now should be 150 perceived or metadata should flag it.
    if verified.metadata.get("total_delay_mins") == 30:
        print("\n✅ TASK 28 VERIFIED: Live delay from Rappid.in successfully injected into route.")
        return True
    else:
        print(f"❌ FAILURE: Delay not correctly captured. Got {verified.metadata.get('total_delay_mins')}")
        return False

if __name__ == "__main__":
    asyncio.run(verify_task_28())
