import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionLocal
from services.hub_route_service import HubRouteService

async def verify_task_34():
    print("=== Verifying Task 34: Alternative Hub-Route Suggestion ===")
    
    db = SessionLocal()
    service = HubRouteService(db)
    
    try:
        # 1. Test Buffer Validation (Task 34.5)
        print("Testing Buffer Validation...")
        arr1 = datetime(2026, 3, 15, 10, 0)
        dep2_ok = datetime(2026, 3, 15, 12, 30) # 2.5 hours
        dep2_bad = datetime(2026, 3, 15, 11, 0) # 1 hour
        
        assert service.validate_hub_connection(arr1, dep2_ok) is True
        assert service.validate_hub_connection(arr1, dep2_bad) is False
        print("[OK] 2-hour buffer enforced correctly")

        # 2. Test Price Difference (Task 34.2)
        print("Testing Price Difference Calculator...")
        diff = service.calculate_price_difference(leg1_fare=500, leg2_fare=400, direct_fare=1200)
        assert diff["total_hub_fare"] == 900
        assert diff["difference"] == -300
        assert diff["is_cheaper"] is True
        print("[OK] Price logic correctly identifies cheaper hub alternatives")

        # 3. Test Hub Suggestion Integration
        print("Testing Hub Suggestion Logic...")
        suggestions = await service.suggest_hub_routes("NDLS", "SBC", "2026-03-15")
        assert len(suggestions) > 0
        assert suggestions[0]["type"] == "HUB_TRANSFER"
        assert "Nagpur" in suggestions[0]["hub_station"]
        assert len(suggestions[0]["legs"]) == 2
        print("[OK] Hub alternatives successfully generated with legs and warnings")

        # 4. Test Hub Booking Initiation (Task 34.4, 34.6)
        print("Testing Hub Multi-Booking Initiation...")
        init_res = await service.initiate_hub_booking("user_123", suggestions[0])
        assert init_res["success"] is True
        assert "HUB-" in init_res["journey_group_id"]
        assert len(init_res["legs"]) == 2
        print("[OK] Multi-booking correctly links legs under a Journey Group ID")

    finally:
        db.close()

    print("=== Task 34 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_34())
