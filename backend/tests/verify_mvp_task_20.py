import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.search_service import SearchService
from database.session import SessionLocal

async def verify_task_20():
    print("\n>>> STARTING VERIFICATION: MVP TASK 20 (ZERO-RESULT EXPLAINER)")
    
    db = SessionLocal()
    search_svc = SearchService(db)
    
    # 1. Test Scenario: Past Date (Subtask 20.2)
    print("\n[20.2] Testing Explainer for Past Date...")
    past_date = datetime.now() - timedelta(days=5)
    res_past = await search_svc.explain_zero_results("NDLS", "KOTA", past_date)
    
    print(f"  Reasons: {res_past['reasons']}")
    print(f"  Suggestions: {res_past['suggestions']}")
    assert "Selected date is in the past." in res_past['reasons']
    assert "Select a future date for travel." in res_past['suggestions']

    # 2. Test Scenario: Too far in Future
    print("\n[20.2] Testing Explainer for Distant Future Date...")
    future_date = datetime.now() + timedelta(days=150)
    res_future = await search_svc.explain_zero_results("NDLS", "KOTA", future_date)
    
    print(f"  Reasons: {res_future['reasons']}")
    assert any("120 days" in r for r in res_future['reasons'])

    # 3. Test Scenario: Disconnected Stations (Subtask 20.3)
    print("\n[20.3] Testing Explainer for Disconnected Stations...")
    # Mocking resolve_stations to return valid stops but with zero direct trains
    # We'll patch the session execute directly
    with patch.object(search_svc.transit_db, 'execute') as mock_exec:
        mock_scalar = MagicMock()
        mock_scalar.scalar.return_value = 0
        mock_exec.return_value = mock_scalar
        
        # Mock station resolution
        s1, s2 = MagicMock(id=1), MagicMock(id=2)
        with patch('services.search_service.resolve_stations', return_value=(s1, s2)):
            res_conn = await search_svc.explain_zero_results("FAKE1", "FAKE2", datetime.now() + timedelta(days=10))
            
            print(f"  Reasons: {res_conn['reasons']}")
            assert "No direct trains found between these stations on any day." in res_conn['reasons']
            print("  SUCCESS: Disconnection reason correctly identified.")

    # 4. Test Integration in search_routes (Subtask 20.4)
    print("\n[20.4] Testing Integration: empty search returns explainer response...")
    with patch('core.route_engine.orchestrator.UnifiedRoutingOrchestrator.search_all_tiers', return_value=[]):
        # Resolve stations must succeed but results empty
        s1, s2 = MagicMock(id=1, latitude=28.6, longitude=77.2), MagicMock(id=2, latitude=19.0, longitude=72.8)
        with patch('services.search_service.resolve_stations', return_value=(s1, s2)):
            # Force zero yield check
            res_integrated = await search_svc.search_routes("NDLS", "KOTA", (datetime.now()+timedelta(days=10)).strftime("%Y-%m-%d"))
            
            print(f"  Integrated Status: {res_integrated.get('status')}")
            assert res_integrated.get("status") == "no_results"
            assert "reasons" in res_integrated
            print("  SUCCESS: search_routes delegated to explainer on zero yield.")

    print("\n✅ ALL MVP TASK 20 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_20())
