import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.search_service import SearchService
from database.session import SessionLocal
from core.data_utils.structures import Route, RouteSegment

async def verify_task_2():
    print("\n>>> STARTING VERIFICATION: MVP TASK 2 (MULTI-DAY EXPANSION)")
    
    db = SessionLocal()
    search_svc = SearchService(db)
    
    # 1. Setup Mock Results
    def create_mock_route(jid, score):
        r = Route()
        r.add_segment(RouteSegment(trip_id=jid, departure_stop_id=1, arrival_stop_id=2, 
                                   departure_time=datetime.now(), arrival_time=datetime.now(),
                                   duration_minutes=100, distance_km=100.0, train_number=jid))
        r.score = score
        return r

    # Target: 5 routes, +1: 10 routes, -1: 10 routes
    target_results = [create_mock_route(f"T{i}", 100+i) for i in range(5)]
    plus_1_results = [create_mock_route(f"P{i}", 200+i) for i in range(10)]
    minus_1_results = [create_mock_route(f"M{i}", 300+i) for i in range(10)]

    async def mock_search_all_tiers(source_code, destination_code, departure_date, constraints, limit, db):
        # Determine which day we are searching
        today = datetime.now().date()
        target = (datetime.now() + timedelta(days=10)).date()
        
        if departure_date.date() == target:
            return target_results
        elif departure_date.date() == target + timedelta(days=1):
            return plus_1_results
        elif departure_date.date() == target - timedelta(days=1):
            return minus_1_results
        return []

    # 2. Test Low Yield Trigger (Subtask 2.1)
    print("\n[2.1 & 2.6] Testing Multi-Day Expansion Trigger...")
    source = "NDLS"
    destination = "KOTA"
    date_str = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    # Patch orchestrator and verification
    with patch('core.route_engine.orchestrator.UnifiedRoutingOrchestrator.search_all_tiers', side_effect=mock_search_all_tiers):
        with patch.object(search_svc, '_verify_routes_parallel', side_effect=lambda routes, dt, q: routes):
            res = await search_svc.search_routes(source, destination, date_str, limit=50)
            
            assert res.get('status') == 'success'
            total_candidates = res['metadata']['total_candidates']
            print(f"  Total Candidates in Unified Pool: {total_candidates}")
            
            # Expected: 5 (Target) + 10 (+1) + 10 (-1) = 25
            assert total_candidates == 25
            print("  SUCCESS: Expansion triggered and results merged.")

            # 3. Verify Date Labels (Subtask 2.5)
            print("\n[2.5] Verifying Day Offset tagging...")
            # Note: journeys in response are masked, let's look at search_svc state if we could
            # but we can infer from the journey_id prefix in the mock
            pool_key = f"search:pool:{res['session_id']}"
            from services.multi_layer_cache import multi_layer_cache
            await multi_layer_cache.initialize()
            
            import json
            # Check Redis for offset data
            data_key = f"search:data:{res['session_id']}"
            all_raw = await multi_layer_cache.redis.hgetall(data_key)
            offsets = []
            for jid_bin, val_bin in all_raw.items():
                jid = jid_bin.decode()
                val = json.loads(val_bin.decode())
                offsets.append(val['metadata'].get('day_offset'))
            
            print(f"  Unique Offsets found: {set(offsets)}")
            assert 0 in offsets
            assert 1 in offsets
            assert -1 in offsets
            print("  SUCCESS: Day offsets correctly preserved in metadata.")

    # 4. Test Past Date Block (Subtask 2.2)
    print("\n[2.2] Testing Past Date search block...")
    # Search for today, expansion to yesterday should be blocked
    date_today_str = datetime.now().strftime("%Y-%m-%d")
    
    async def mock_search_today(source_code, destination_code, departure_date, constraints, limit, db):
        return [create_mock_route("TODAY", 10)] # low yield

    with patch('core.route_engine.orchestrator.UnifiedRoutingOrchestrator.search_all_tiers', side_effect=mock_search_today):
        with patch.object(search_svc, '_verify_routes_parallel', side_effect=lambda routes, dt, q: routes):
            res_today = await search_svc.search_routes(source, destination, date_today_str)
            
            data_key_today = f"search:data:{res_today['session_id']}"
            all_raw_today = await multi_layer_cache.redis.hgetall(data_key_today)
            offsets_today = [json.loads(v.decode())['metadata'].get('day_offset') for v in all_raw_today.values()]
            
            print(f"  Offsets for today's search: {set(offsets_today)}")
            assert -1 not in offsets_today
            print("  SUCCESS: Past-date expansion correctly blocked.")

    print("\n✅ ALL MVP TASK 2 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_2())
