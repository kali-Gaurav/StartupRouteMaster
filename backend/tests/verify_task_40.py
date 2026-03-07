import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.search_service import SearchService
from core.data_structures import Route, RouteSegment, Persona

async def verify_task_40():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 40 (PAGINATION)")
    
    # 1. Setup Mock DB and Service
    db = MagicMock()
    service = SearchService(db)
    
    # 2. Mock a list of 25 routes
    mock_routes = []
    for i in range(25):
        r = Route(score=i)
        r.add_segment(RouteSegment(
            trip_id=i, departure_stop_id=1, arrival_stop_id=2,
            departure_time=datetime.now(), arrival_time=datetime.now(),
            duration_minutes=60, distance_km=100, train_number=f"T{i}"
        ))
        mock_routes.append(r)
        
    # Mock internal methods to bypass heavy computation
    service._verify_routes_parallel = AsyncMock(return_value=mock_routes)
    from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
    service.orchestrator = MagicMock(spec=UnifiedRoutingOrchestrator)
    service.orchestrator.search_all_tiers = AsyncMock(return_value=[]) # search_routes will use verified_routes mock
    
    # Station resolution mock
    import services.search_service as search_svc_mod
    search_svc_mod.resolve_stations = MagicMock(return_value=(MagicMock(id=1), MagicMock(id=2)))
    
    # Mock ML availability
    from unittest.mock import patch
    with patch('services.ml.availability_heuristic.availability_heuristic') as mock_ml:
        mock_ml.get_route_availability_score.return_value = 0.9
        
        print("  Testing Page 1 (Limit 10)...")
        # ACT: Page 1
        res1 = await service.search_routes("NDLS", "BCT", "2026-03-08", page=1, limit=10)
        
        print(f"    Page 1 Journeys: {len(res1['data']['journeys'])}")
        print(f"    Grouped Journeys present: {len(res1['data']['grouped_journeys']) > 0}")
        print(f"    Has Next: {res1['data']['pagination']['has_next']}")
        
        assert len(res1['data']['journeys']) == 10
        assert len(res1['data']['grouped_journeys']) > 0
        assert res1['data']['pagination']['has_next'] == True
        assert res1['data']['pagination']['total_results'] == 25
        
        # ACT: Page 2
        print("\n  Testing Page 2 (Limit 10)...")
        res2 = await service.search_routes("NDLS", "BCT", "2026-03-08", page=2, limit=10)
        
        print(f"    Page 2 Journeys: {len(res2['data']['journeys'])}")
        print(f"    Grouped Journeys empty: {len(res2['data']['grouped_journeys']) == 0}")
        print(f"    Has Next: {res2['data']['pagination']['has_next']}")
        
        assert len(res2['data']['journeys']) == 10
        assert len(res2['data']['grouped_journeys']) == 0
        assert res2['data']['pagination']['has_next'] == True
        
        # ACT: Page 3 (Last 5)
        print("\n  Testing Page 3 (Limit 10)...")
        res3 = await service.search_routes("NDLS", "BCT", "2026-03-08", page=3, limit=10)
        
        print(f"    Page 3 Journeys: {len(res3['data']['journeys'])}")
        print(f"    Has Next: {res3['data']['pagination']['has_next']}")
        
        assert len(res3['data']['journeys']) == 5
        assert res3['data']['pagination']['has_next'] == False
    
    print("\n✅ TASK 40 FULLY VERIFIED: Pagination logic is robust.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(verify_task_40())
