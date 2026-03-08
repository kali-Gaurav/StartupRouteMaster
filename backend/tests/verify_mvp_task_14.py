import asyncio
import sys
import os
import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.search_service import SearchService
from database.session import SessionLocal
from core.data_structures import Route, RouteSegment

async def verify_task_14():
    logging.basicConfig(level=logging.INFO)
    print("\n>>> STARTING VERIFICATION: MVP TASK 14 (PARTIAL RESCUE)")
    
    db = SessionLocal()
    search_svc = SearchService(db)
    
    # 1. Setup Mock Route (Single leg for simplicity of trigger)
    r1 = Route()
    s1 = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=datetime.now(), arrival_time=datetime.now() + timedelta(hours=2),
                      duration_minutes=120, distance_km=100.0, train_number="T14_RESCUE")
    r1.add_segment(s1)
    
    # 2. Mock DataProvider to fail first attempt, succeed second
    mock_seat_fail = {"status": "error", "message": "Transient Error"}
    mock_seat_success = {"status": "verified", "available_seats": 10, "source": "rapidapi", "availability": "AVAILABLE 10"}
    mock_fare = {"total_fare": 500.0}
    mock_status = {"delay_mins": 0}

    call_count = 0
    async def mock_seat_logic(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_seat_fail
        return mock_seat_success

    with patch.object(search_svc.data_provider, 'verify_seat_availability_unified', side_effect=mock_seat_logic):
        with patch.object(search_svc.data_provider, 'verify_fare_unified', return_value=mock_fare):
            with patch.object(search_svc.data_provider, 'get_live_status', return_value=mock_status):
                
                print("  Executing verification with transient failure...")
                # Use travel date today
                verified_route = await search_svc._verify_single_route_logic(r1, datetime.now())
                
                # 3. Verify Rescue
                print(f"    DataProvider Calls: {call_count}")
                print(f"    Is Verified: {verified_route.metadata.get('is_verified')}")
                print(f"    Availability Prob: {verified_route.availability_probability}")
                
                # Should have called twice
                assert call_count == 2
                assert verified_route.metadata.get('is_verified') is True
                assert verified_route.availability_probability > 0.9
                print("  SUCCESS: Leg salvaged after transient failure.")

    print("\n✅ ALL MVP TASK 14 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_14())
