import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.search_service import SearchService
from database.session import SessionLocal
from core.data_utils.structures import Route, RouteSegment

async def verify_task_17():
    print("\n>>> STARTING VERIFICATION: MVP TASK 17 (ASYNC STREAMING)")
    
    db = SessionLocal()
    search_svc = SearchService(db)
    
    # 1. Setup Mock Routes
    def create_mock_route(jid):
        r = Route()
        s = RouteSegment(trip_id=jid, departure_stop_id=1, arrival_stop_id=2, 
                          departure_time=datetime.now(), arrival_time=datetime.now(),
                          duration_minutes=100, distance_km=100.0, train_number=f"T{jid}")
        r.add_segment(s)
        r.score = 100.0
        return r

    # 10 routes total
    mock_search_res = [create_mock_route(f"ST_{i}") for i in range(10)]

    # 2. Execute Streaming Search
    print("\n[17.1 & 17.2] Consuming search_routes_stream generator...")
    
    source, destination = "NDLS", "KOTA"
    date_str = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    with patch('core.route_engine.orchestrator.UnifiedRoutingOrchestrator.search_all_tiers', return_value=mock_search_res):
        # Mock verification to succeed immediately
        async def mock_verify(routes, dt, q):
            for r in routes: r.metadata["is_verified"] = True
            return routes
            
        with patch.object(search_svc, '_verify_routes_parallel', side_effect=mock_verify):
            
            events = []
            async for chunk in search_svc.search_routes_stream(source, destination, date_str):
                events.append(chunk)
                print(f"  Event Received: {chunk.get('status')} | Progress: {chunk.get('progress', 0)}%")

            # 3. Verify Event Sequence
            print(f"\n  Total Events: {len(events)}")
            
            statuses = [e.get("status") for e in events]
            print(f"  Status Sequence: {statuses}")
            
            assert statuses[0] == "searching"
            assert statuses[1] == "discovered"
            assert "partial_results" in statuses
            assert statuses[-1] == "complete"
            
            # Since chunk_size=3 and we have 10 routes:
            # 10/3 = 4 partial result events expected
            partial_count = statuses.count("partial_results")
            print(f"  Partial Result Chunks: {partial_count}")
            assert partial_count >= 4
            
            # Check progress logic
            last_partial = [e for e in events if e.get("status") == "partial_results"][-1]
            assert last_partial["progress"] == 100.0
            print("  SUCCESS: Progress tracking at 100% on last chunk.")

    print("\n✅ ALL MVP TASK 17 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_17())
