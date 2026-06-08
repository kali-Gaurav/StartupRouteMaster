import asyncio
import logging
import sys
import os
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.search_service import SearchService
from database.session import SessionLocal
from core.data_utils.structures import Route, RouteSegment

async def verify_task_1():
    print("\n>>> STARTING VERIFICATION: MVP TASK 1 (PAGINATION & VERIFICATION)")
    
    db = SessionLocal()
    search_svc = SearchService(db)
    
    # 1. Test Initial Search (Subtask 1.1)
    print("\n[1.1] Testing Initial Search NDLS -> KOTA...")
    source = "NDLS"
    destination = "KOTA"
    date_str = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    # We'll patch _verify_routes_parallel to avoid real API hits
    async def mock_verify(routes, dt, q):
        return routes

    with patch.object(search_svc, '_verify_routes_parallel', side_effect=mock_verify):
        res1 = await search_svc.search_routes(source, destination, date_str, limit=5)
        
        print(f"  Status: {res1.get('status')}")
        assert res1.get('status') == 'success'
        
        data = res1.get('data', {})
        journeys1 = data.get('journeys', [])
        next_cursor = data.get('next_cursor')
        session_id = res1.get('session_id')
        
        print(f"  Found {len(journeys1)} initial journeys.")
        print(f"  Next Cursor: {next_cursor}")
        print(f"  Session ID: {session_id}")
        
        assert len(journeys1) > 0
        assert next_cursor is not None
        assert session_id is not None

        # 2. Test Load More (Subtask 1.3)
        print("\n[1.3] Testing Load More with Cursor...")
        res2 = await search_svc.load_more_routes(session_id, limit=5, cursor=next_cursor)
        
        assert res2.get('status') == 'success'
        journeys2 = res2.get('data', {}).get('journeys', [])
        print(f"  Found {len(journeys2)} additional journeys.")
        
        # 3. Duplicate Prevention (Subtask 1.5)
        print("\n[1.5] Verifying zero duplicates across pages...")
        jid1 = set(j['journey_id'] for j in journeys1)
        jid2 = set(j['journey_id'] for j in journeys2)
        
        duplicates = jid1.intersection(jid2)
        print(f"  Duplicate IDs: {duplicates}")
        assert len(duplicates) == 0
        print("  SUCCESS: No duplicates found.")

    # 4. Test Verification Batching (Subtask 1.8)
    print("\n[1.8] Testing Verification Batching logic...")
    dummy_routes = []
    for i in range(12):
        r = Route()
        r.add_segment(RouteSegment(trip_id=i, departure_stop_id=1, arrival_stop_id=2, 
                                   departure_time=datetime.now(), arrival_time=datetime.now()+timedelta(hours=2),
                                   duration_minutes=120, distance_km=100.0, train_number=f"T{i}"))
        dummy_routes.append(r)
    
    start_v = time.time()
    # Mock _verify_single_route to return immediately
    with patch.object(search_svc, '_verify_single_route', side_effect=lambda r, dt, q: r):
        verified = await search_svc._verify_routes_parallel(dummy_routes, datetime.now())
        duration = time.time() - start_v
        print(f"  Verified 12 routes in {duration:.4f}s")
        # Since we have batches of 5, for 12 routes:
        # Batch 1 (5), Batch 2 (5), Batch 3 (2)
        # 2 sleeps of 200ms = 400ms minimum
        assert duration >= 0.4
        print("  SUCCESS: Batching delay detected (at least 2x200ms).")

    # 5. Test Fallback (Subtask 1.9)
    print("\n[1.9] Testing Timeout Fallback to Heuristic...")
    # Create a route that will timeout
    r_timeout = Route()
    r_timeout.add_segment(RouteSegment(trip_id=999, departure_stop_id=1, arrival_stop_id=2, 
                                       departure_time=datetime.now(), arrival_time=datetime.now()+timedelta(hours=2),
                                       duration_minutes=120, distance_km=100.0, train_number="SLOW_T"))
    
    async def slow_verify(*args, **kwargs):
        await asyncio.sleep(5)
        return r_timeout

    with patch.object(search_svc, '_verify_single_route_logic', side_effect=slow_verify):
        with patch('services.ml.availability_heuristic.availability_heuristic.get_route_availability_score', return_value=0.85):
            res_v = await search_svc._verify_single_route(r_timeout, datetime.now())
            print(f"  Fallback Result: is_estimated={res_v.metadata.get('is_estimated')}, prob={res_v.availability_probability}")
            assert res_v.metadata.get('is_estimated') is True
            assert res_v.availability_probability == 0.85
            print("  SUCCESS: Graceful fallback to ML heuristic.")

    print("\n✅ ALL MVP TASK 1 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_1())
