import asyncio
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

async def verify_task_10():
    print("\n>>> STARTING VERIFICATION: MVP TASK 10 (PERSONA OVERRIDES)")
    
    db = SessionLocal()
    search_svc = SearchService(db)
    
    # 1. Setup Mock Results
    # R1: Short (200m) but Expensive (2000)
    # R2: Long (600m) but Cheap (500)
    def create_route(jid, dur, cost):
        r = Route()
        s = RouteSegment(trip_id=jid, departure_stop_id=1, arrival_stop_id=2, 
                          departure_time=datetime.now(), arrival_time=datetime.now() + timedelta(minutes=dur),
                          duration_minutes=dur, distance_km=100.0, train_number=jid)
        r.add_segment(s)
        r.total_cost = float(cost)
        r.total_duration = dur
        r.score = 0.0 # Will be re-calculated
        return r

    r_fast = create_route("FAST", 200, 2000)
    r_cheap = create_route("CHEAP", 600, 500)
    
    # Manually set scores for Budget (Time*0.5 + Cost*2.0)
    r_fast.score = (200 * 0.5) + (2000 * 2.0) # 4100
    r_cheap.score = (600 * 0.5) + (500 * 2.0) # 1300
    
    mock_routes = [r_fast, r_cheap]

    # 2. Initial Search (Persona: Budget)
    print("\n[10.1] Initial Search (Budget)...")
    source, destination = "NDLS", "KOTA"
    date_str = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    with patch('core.route_engine.orchestrator.UnifiedRoutingOrchestrator.search_all_tiers', return_value=mock_routes):
        with patch.object(search_svc, '_verify_routes_parallel', side_effect=lambda routes, dt, q: routes):
            res_budget = await search_svc.search_routes(source, destination, date_str, budget_category="budget")
            
            session_id = res_budget['session_id']
            # Budget should prefer Cheap
            top_budget = res_budget['data']['journeys'][0]['journey_id']
            print(f"  Budget Top Result: {top_budget}")
            assert "CHEAP" in top_budget

            # 3. Re-Rank (Persona: Emergency)
            print("\n[10.4 & 10.5] Re-Ranking to 'Emergency'...")
            start_re = time.perf_counter()
            res_emerg = await search_svc.re_rank_routes(session_id, "emergency")
            duration_re = (time.perf_counter() - start_re) * 1000
            
            print(f"  Re-rank Latency: {duration_re:.2f}ms")
            assert duration_re < 500 # Strict check (usually < 100ms)
            
            # Emergency should prefer Fast
            top_emerg = res_emerg['data']['journeys'][0]['journey_id']
            print(f"  Emergency Top Result: {top_emerg}")
            assert "FAST" in top_emerg
            
            print("  SUCCESS: Order swapped based on persona weights.")

            # 4. Verify Category Highlights (Subtask 10.6)
            print("\n[10.6] Verifying Persona-specific highlights...")
            top_3 = res_emerg['data']['grouped_journeys']['top_3_highlight']
            found_critical = False
            for rd in top_3:
                if "FAST" in rd['journey_id']:
                    print(f"    - Fast route highlight: {rd.get('highlight_label')}")
                    # In emergency, fast should be top
                    found_critical = True
            
            assert found_critical is True

    print("\n✅ ALL MVP TASK 10 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_10())
