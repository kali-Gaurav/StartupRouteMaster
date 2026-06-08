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

async def verify_task_9():
    logging.basicConfig(level=logging.INFO)
    print("\n>>> STARTING VERIFICATION: MVP TASK 9 (QUOTA SUGGESTIONS)")
    
    db = SessionLocal()
    search_svc = SearchService(db)
    
    # 1. Setup Mock for High-Risk GN search
    def create_mock_route(jid, prob, quota="GN"):
        r = Route()
        s = RouteSegment(trip_id=jid, departure_stop_id=1, arrival_stop_id=2, 
                          departure_time=datetime.now(), arrival_time=datetime.now(),
                          duration_minutes=100, distance_km=100.0, train_number=f"T{jid}")
        r.add_segment(s)
        r.availability_probability = prob
        r.score = 100.0
        r.metadata["quota"] = quota
        return r

    # Return 10 routes with 0.2 probability (High Risk)
    gn_results = [create_mock_route(f"GN_{i}", 0.2) for i in range(10)]
    # Return 5 routes with 0.9 probability for Tatkal
    tq_results = [create_mock_route(f"TQ_{i}", 0.9, "TQ") for i in range(5)]

    async def mock_search_dispatch(source_code, destination_code, departure_date, constraints, limit, db):
        # We'll differentiate based on constraints or caller
        # In search_service, we don't change constraints for Tatkal search yet
        # But we can track call count
        if not hasattr(mock_search_dispatch, "calls"):
            mock_search_dispatch.calls = 0
        
        mock_search_dispatch.calls += 1
        if mock_search_dispatch.calls == 1:
            return gn_results
        else:
            return tq_results

    # 2. Test Trigger Logic
    print("\n[9.2 & 9.3] Testing auto-trigger of Tatkal search...")
    source = "NDLS"
    destination = "KOTA"
    date_str = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    # Patch orchestrator
    with patch('core.route_engine.orchestrator.UnifiedRoutingOrchestrator.search_all_tiers', side_effect=mock_search_dispatch) as mock_orch:
        # Mock verification to preserve our probabilities
        async def mock_verify(routes, dt, q):
            # If quota is TQ, return high prob, else low
            for r in routes:
                if q == "TQ":
                    r.availability_probability = 0.9
                    r.metadata["quota"] = "TQ"
                else:
                    r.availability_probability = 0.2
            return routes

        with patch.object(search_svc, '_verify_routes_parallel', side_effect=mock_verify):
            
            res = await search_svc.search_routes(source, destination, date_str)
            
            assert res.get('status') == 'success'
            
            # 3. Verify Tatkal Presence (Subtask 9.4)
            print("\n[9.4] Verifying presence of Tatkal alternatives in response...")
            journeys = res['data']['journeys']
            
            # Since we merged them, some should have quota='TQ'
            # Note: response is masked, but we can check session data
            from services.multi_layer_cache import multi_layer_cache
            await multi_layer_cache.initialize()
            data_key = f"search:data:{res['session_id']}"
            all_raw = await multi_layer_cache.redis.hgetall(data_key)
            
            tq_count = 0
            for val_bin in all_raw.values():
                import json
                val = json.loads(val_bin.decode())
                if val['metadata'].get('quota') == "TQ":
                    tq_count += 1
                    print(f"  SUCCESS: Found Tatkal Alt {val['journey_id']} with label: {val['metadata'].get('ui_reasons')}")
                    assert "High Availability Alternative (Tatkal)" in val['metadata'].get('ui_reasons')
            
            assert tq_count > 0
            print(f"  Total Tatkal Alternatives found: {tq_count}")

    print("\n✅ ALL MVP TASK 9 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_9())
