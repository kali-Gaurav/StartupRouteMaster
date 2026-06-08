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
from core.data_utils.structures import Route, RouteSegment

async def verify_task_15():
    logging.basicConfig(level=logging.INFO)
    print("\n>>> STARTING VERIFICATION: MVP TASK 15 (FARE ANOMALY)")
    
    db = SessionLocal()
    search_svc = SearchService(db)
    
    # 1. Setup Mock Route (Single leg)
    r1 = Route()
    s1 = RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                      departure_time=datetime.now(), arrival_time=datetime.now() + timedelta(hours=2),
                      duration_minutes=120, distance_km=1000.0, train_number="T15_ANOMALY",
                      departure_code="NDLS", arrival_code="BOM")
    r1.add_segment(s1)
    
    # 2. Mock DataProvider to return an EXTREMELY HIGH fare
    # Distance 1000km, expected ~1200 (SL), API returns 5000
    mock_seat = {"status": "verified", "available_seats": 5, "availability": "AVAILABLE 5"}
    mock_fare_anomaly = {"total_fare": 5000.0}
    mock_status = {"delay_mins": 0}

    with patch.object(search_svc.data_provider, 'verify_seat_availability_unified', return_value=mock_seat):
        with patch.object(search_svc.data_provider, 'verify_fare_unified', return_value=mock_fare_anomaly):
            with patch.object(search_svc.data_provider, 'get_live_status', return_value=mock_status):
                
                print("  Executing verification with fare anomaly (API=5000 vs Calc~1200)...")
                verified_route = await search_svc._verify_single_route_logic(r1, datetime.now())
                
                # 3. Verify Anomaly Flagging
                print(f"    Is Anomaly: {verified_route.metadata.get('is_anomaly')}")
                print(f"    Anomaly Reason: {verified_route.metadata.get('anomaly_reason')}")
                
                assert verified_route.metadata.get("is_anomaly") is True
                assert verified_route.metadata.get("anomaly_reason") == "SUSPICIOUS_FARE"
                print("  SUCCESS: Fare anomaly correctly detected and flagged.")

    # 4. Test Normal Fare (No Anomaly)
    mock_fare_normal = {"total_fare": 700.0} # Within 30% of ~633
    r2 = Route()
    r2.add_segment(s1)
    with patch.object(search_svc.data_provider, 'verify_fare_unified', return_value=mock_fare_normal):
        verified_route_new = await search_svc._verify_single_route_logic(r2, datetime.now())
        assert verified_route_new.metadata.get("is_anomaly") is None
        print("  SUCCESS: Normal fare passed without anomaly flagging on fresh route.")

    print("\n✅ ALL MVP TASK 15 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_15())
