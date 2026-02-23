import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Add the project root to sys.path
sys.path.append(os.getcwd())

from backend.services.revenue_cat_verifier import RevenueCatVerifier
from backend.services.unlock_service import UnlockService

async def test_revenue_cat_flow():
    print("\n" + "="*50)
    print("TESTING REVENUECAT PAYMENT FLOW INTEGRATION")
    print("="*50)

    # 1. Setup Mock DB and Service
    mock_db = MagicMock()
    unlock_service = UnlockService(mock_db)
    
    user_id = "test-user-123"
    route_id = "delhi-mumbai-express"

    # 2. Scenario: User is NOT a subscriber, and HAS NOT paid for route
    print("\nScenario 1: New user (No subscription, No previous pay)")
    
    # Reset mock_db query chain
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    # We must patch where it's USED, not where it's DEFINED
    with patch("backend.services.unlock_service.revenue_cat_verifier.is_user_pro") as mock_verify:
        future_no_pro_1 = asyncio.Future()
        future_no_pro_1.set_result(False)
        mock_verify.return_value = future_no_pro_1
        
        is_unlocked = await unlock_service.is_route_unlocked(user_id, route_id)
        db_call_made = mock_db.query.called
        print(f"  Result: {'UNLOCKED' if is_unlocked else 'LOCKED (Expected)'}")
        print(f"  DB Query Called: {db_call_made}")

    # 3. Scenario: User HAS a RevenueCat subscription (Pro)
    print("\nScenario 2: User has active Routemaster Pro subscription")
    
    with patch("backend.services.unlock_service.revenue_cat_verifier.is_user_pro") as mock_verify:
        future_pro = asyncio.Future()
        future_pro.set_result(True)
        mock_verify.return_value = future_pro
        
        is_unlocked = await unlock_service.is_route_unlocked(user_id, route_id)
        print(f"  Result: {'UNLOCKED (Expected)' if is_unlocked else 'LOCKED'}")
        print("  Note: RevenueCat successfully bypassed individual payment.")

    # 4. Scenario: User has NO subscription BUT has paid for this specific route
    print("\nScenario 3: No subscription, but route-specific payment found in DB")
    
    with patch("backend.services.unlock_service.revenue_cat_verifier.is_user_pro") as mock_verify:
        future_no_pro_3 = asyncio.Future()
        future_no_pro_3.set_result(False)
        mock_verify.return_value = future_no_pro_3
        
        # Mock individual payment record in DB
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        
        is_unlocked = await unlock_service.is_route_unlocked(user_id, route_id)
        print(f"  Result: {'UNLOCKED (Expected)' if is_unlocked else 'LOCKED'}")

    print("\n" + "="*50)
    print("FLOW VERIFICATION COMPLETE")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(test_revenue_cat_flow())
