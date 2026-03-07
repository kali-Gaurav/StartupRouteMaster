import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.search_service import SearchService
from core.data_structures import Route, RouteSegment

async def verify_task_37():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 37 (PLATFORM TRACKING)")
    
    # Mock dependencies
    db = MagicMock()
    service = SearchService(db)
    
    # 1. Mock DataProvider to return platform info
    mock_status = {
        "delay_mins": 10,
        "platform": "8",
        "current_station": "CNB"
    }
    service.data_provider.get_live_status = AsyncMock(return_value=mock_status)
    service.data_provider.verify_seat_availability_unified = AsyncMock(return_value={"available_seats": 10})
    service.data_provider.verify_fare_unified = AsyncMock(return_value={"total_fare": 500.0})

    # 2. Create route with 1 segment
    r = Route()
    r.add_segment(RouteSegment(
        trip_id=1, departure_stop_id=1, arrival_stop_id=2,
        departure_time=datetime.now(), arrival_time=datetime.now(),
        duration_minutes=60, distance_km=100, train_number="12625"
    ))
    
    # 3. Verify
    print("  Triggering live platform hydration...")
    verified = await service._verify_single_route(r, datetime.now())
    
    seg = verified.segments[0]
    print(f"  Segment Platforms: Dep={seg.departure_platform}, Arr={seg.arrival_platform}")
    print(f"  Metadata: {seg.metadata}")
    
    assert seg.arrival_platform == "8"
    assert seg.metadata.get("pf_verified") == True
    
    # 4. Check serialization
    d = verified.to_dict()
    assert d["segments"][0]["arrival_platform"] == "8"
    
    print("\n✅ TASK 37 FULLY VERIFIED")

if __name__ == "__main__":
    import asyncio
    asyncio.run(verify_task_37())
