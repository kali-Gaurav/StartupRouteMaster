import asyncio
import os
import sys
import logging
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.data_structures import Route, RouteSegment
from services.search_service import SearchService
from database.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_task_27")

async def verify_task_27():
    print("\n>>> Verifying Task 27: Predictive Availability & ML Ranking")
    
    db = SessionLocal()
    service = SearchService(db)
    
    # 1. Create two mock routes
    # Route A: High CNF Prob
    # Route B: Low CNF Prob (< 20%)
    
    # Use patch to mock the heuristic result
    with patch('services.ml.availability_heuristic.availability_heuristic.get_route_availability_score') as mock_ml:
        # First call: 0.9 (Safe), Second call: 0.1 (Risky)
        mock_ml.side_effect = [0.9, 0.1]
        
        # We need to mock the Orchestrator to return 2 routes
        from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
        with patch.object(UnifiedRoutingOrchestrator, 'search_all_tiers', new_callable=AsyncMock) as mock_search:
            r1 = Route(segments=[RouteSegment(1, 1, 2, datetime.now(), datetime.now(), 100, 100.0, "S1", "S2", 500.0, "T1", "12345")])
            r2 = Route(segments=[RouteSegment(2, 3, 4, datetime.now(), datetime.now(), 100, 100.0, "S3", "S4", 500.0, "T2", "67890")])
            mock_search.return_value = [r1, r2]
            
            # Disable real verification for this test
            service._verify_routes_parallel = AsyncMock(side_effect=lambda routes, dt, quota: routes)
            
            print("  Running search with ML pruning active...")
            res = await service.search_routes("NDLS", "BCT", "2026-03-08")
            
            journeys = res.get("journeys", [])
            print(f"  Total journeys after pruning: {len(journeys)}")
            
            # Verify Pruning (Task 27.4)
            if len(journeys) != 1:
                print(f"❌ FAILURE: Expected 1 journey (pruned the 10% one), got {len(journeys)}")
                return False
            
            # Verify Ranking (Task 27.5)
            best_jid = journeys[0].get("journey_id")
            print(f"  Best Journey: {best_jid} (Prob: {journeys[0].get('availability_prob')})")
            
            if "12345" in best_jid:
                print("\n✅ TASK 27 VERIFIED: ML Pruning and Ranking are operational.")
                return True
            else:
                print("❌ FAILURE: Ranked the wrong route as best.")
                return False

if __name__ == "__main__":
    from datetime import datetime
    from unittest.mock import AsyncMock
    asyncio.run(verify_task_27())
