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
from services.multi_layer_cache import multi_layer_cache

async def verify_task_18():
    print("\n>>> STARTING VERIFICATION: MVP TASK 18 (QUOTA SEGMENTATION)")
    
    await multi_layer_cache.initialize()
    if not multi_layer_cache.redis:
        print("  REDIS NOT AVAILABLE. SKIPPING.")
        return

    db = SessionLocal()
    search_svc = SearchService(db)
    
    source, destination = "NDLS", "KOTA"
    date_str = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    session_id = "test_seg_18"

    # 1. Mock searches for GN and TQ
    async def mock_orch(source_code, destination_code, departure_date, constraints, limit, db):
        # Return simple route
        from core.data_utils.structures import Route, RouteSegment
        r = Route()
        r.add_segment(RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
                                   departure_time=datetime.now(), arrival_time=datetime.now(),
                                   duration_minutes=100, distance_km=100.0, train_number="12625"))
        r.score = 100.0
        return [r]

    with patch('core.route_engine.orchestrator.UnifiedRoutingOrchestrator.search_all_tiers', side_effect=mock_orch):
        with patch.object(search_svc, '_verify_routes_parallel', side_effect=lambda routes, dt, q: routes):
            
            print("  Searching with Quota: GN...")
            res_gn = await search_svc.search_routes(source, destination, date_str, quota="GN", session_id=session_id)
            
            print("  Searching with Quota: TQ...")
            res_tq = await search_svc.search_routes(source, destination, date_str, quota="TQ", session_id=session_id)

            # 2. Verify Redis Keys
            print("\n[18.2] Verifying Redis key isolation...")
            r = multi_layer_cache.redis
            
            # Keys should contain quota
            key_gn = f"search:pool:GN:{session_id}"
            key_tq = f"search:pool:TQ:{session_id}"
            
            exists_gn = await r.exists(key_gn)
            exists_tq = await r.exists(key_tq)
            
            print(f"  GN Key exists: {exists_gn}")
            print(f"  TQ Key exists: {exists_tq}")
            
            assert exists_gn == 1
            assert exists_tq == 1
            assert key_gn != key_tq
            print("  SUCCESS: Redis keys are quota-segmented.")

            # 3. Test Load More Isolation
            print("\n[18.3] Verifying load_more isolation...")
            # If I load more for GN, it should hit key_gn
            res_load_gn = await search_svc.load_more_routes(session_id, quota="GN")
            assert res_load_gn.get("status") == "success"
            
            # If I try a bogus quota, it should miss
            res_load_bogus = await search_svc.load_more_routes(session_id, quota="BOGUS")
            # Bogus quota won't exist in Redis
            assert res_load_bogus.get("data", {}).get("journeys") == []
            print("  SUCCESS: Load more respects quota segmentation.")

    print("\n✅ ALL MVP TASK 18 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_18())
