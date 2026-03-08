import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.search_service import SearchService
from database.session import SessionLocal
from core.data_structures import Route, RouteSegment

async def verify_task_6():
    print("\n>>> STARTING VERIFICATION: MVP TASK 6 (HUB FALLBACK)")
    
    db = SessionLocal()
    search_svc = SearchService(db)
    
    # 1. Setup Mock for Hub Fallback
    # Logic: If source is 'REMOTE_SRC' and dest is 'BPL', return a leg.
    #        If source is 'BPL' and dest is 'REMOTE_DST', return a leg.
    #        Otherwise return []
    
    def create_mock_leg(src, dst, is_first):
        r = Route()
        # Ensure leg 2 departs after leg 1 arrives
        dep = datetime.now() if is_first else datetime.now() + timedelta(hours=5)
        arr = dep + timedelta(hours=2)
        s = RouteSegment(trip_id=f"T_{src}_{dst}", departure_stop_id=1, arrival_stop_id=2, 
                          departure_code=src, arrival_code=dst,
                          departure_time=dep, arrival_time=arr,
                          duration_minutes=120, distance_km=100.0, train_number=f"TR_{src}_{dst}")
        r.add_segment(s)
        r.score = 100.0
        return [r]

    async def mock_hub_search(source_code, destination_code, departure_date, constraints, limit, db):
        # We simulate a connection via 'BPL' (Bhopal)
        if source_code == "REMOTE_SRC" and destination_code == "BPL":
            return create_mock_leg("REMOTE_SRC", "BPL", True)
        if source_code == "BPL" and destination_code == "REMOTE_DST":
            return create_mock_leg("BPL", "REMOTE_DST", False)
        return []

    # 2. Test Fallback Trigger
    print("\n[6.2 & 6.4] Testing Hub Fallback for Remote stations...")
    source = "REMOTE_SRC"
    destination = "REMOTE_DST"
    date_str = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    # Patch orchestrator and verification
    # Also need to mock station resolution for mock stations
    with patch('services.search_service.resolve_stations') as mock_resolve:
        # Mock station objects
        s1 = MagicMock(latitude=23.0, longitude=77.0) # Near BPL
        s2 = MagicMock(latitude=24.0, longitude=78.0) # Near BPL
        mock_resolve.return_value = (s1, s2)
        
        with patch('core.route_engine.orchestrator.UnifiedRoutingOrchestrator.search_all_tiers', side_effect=mock_hub_search):
            with patch.object(search_svc, '_verify_routes_parallel', side_effect=lambda routes, dt, q: routes):
                
                res = await search_svc.search_routes(source, destination, date_str)
                
                assert res.get('status') == 'success'
                journeys = res['data']['journeys']
                print(f"  Found {len(journeys)} fallback journeys.")
                
                # Verify it's a hub fallback route
                # Note: Response is masked, check session pool data
                from services.multi_layer_cache import multi_layer_cache
                await multi_layer_cache.initialize()
                data_key = f"search:data:{res['session_id']}"
                all_raw = await multi_layer_cache.redis.hgetall(data_key)
                
                found_fallback = False
                for val_bin in all_raw.values():
                    import json
                    val = json.loads(val_bin.decode())
                    if val['metadata'].get('engine') == "hub_fallback":
                        found_fallback = True
                        print(f"  SUCCESS: Found hub_fallback route via {val['transfers'][0]['station_name']}")
                        assert len(val['segments']) == 2
                        assert val['metadata'].get('is_discovery') is True
                
                assert found_fallback is True

    print("\n✅ ALL MVP TASK 6 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_6())
