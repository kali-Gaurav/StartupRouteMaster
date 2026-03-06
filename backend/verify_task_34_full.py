import sys
import os
import asyncio
import uuid
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionLocal
from services.hub_route_service import HubRouteService
from database.models import User, Booking

async def verify_task_34_full():
    print("=== Verifying Task 34: COMPLETE Hub-Route Integration ===")
    
    db = SessionLocal()
    service = HubRouteService(db)
    
    try:
        user_id = str(uuid.uuid4())
        user = User(id=user_id, email=f"hub_{user_id}@example.com")
        db.add(user)
        db.commit()

        # 1. Suggest Hub Routes (Task 34.1, 34.2, 34.3, 34.5, 34.7, 34.8)
        print("Step 1: Suggesting Hub Routes...")
        
        # Mock the engine call since we don't have the 460MB transit DB loaded for the test
        from core.route_engine import route_engine
        from core.route_engine.data_structures import Route, RouteSegment, TransferConnection
        
        async def mock_search(*args, **kwargs):
            r = Route(segments=[
                RouteSegment(trip_id="12625", departure_stop_id=1, arrival_stop_id=2, departure_time=datetime(2026, 3, 15, 10, 0), arrival_time=datetime(2026, 3, 15, 14, 0), fare=450.0, duration_minutes=240, distance_km=500.0),
                RouteSegment(trip_id="12245", departure_stop_id=2, arrival_stop_id=3, departure_time=datetime(2026, 3, 15, 17, 30), arrival_time=datetime(2026, 3, 15, 20, 0), fare=600.0, duration_minutes=150, distance_km=300.0)
            ])
            tr = TransferConnection(
                station_id=2, 
                arrival_time=datetime(2026, 3, 15, 14, 0), 
                departure_time=datetime(2026, 3, 15, 17, 30), 
                duration_minutes=210,
                station_name="Nagpur",
                facilities_score=5.0,
                safety_score=5.0
            )
            r.transfers = [tr]
            r.metadata = {"platforms": {"hub_arrival": "3", "hub_departure": "1"}}
            return [r]
            
        route_engine.search_hub_routes = mock_search
        
        suggestions = await service.suggest_hub_routes("NDLS", "SBC", "2026-03-15")
        assert len(suggestions) > 0
        s = suggestions[0]
        assert s["type"] == "HUB_TRANSFER"
        assert "price_info" in s
        assert "warnings" in s
        assert "platform_info" in s
        print(f"[OK] Hub route suggested with price savings: {s['price_info']['difference']}")

        # 2. Initiate Hub Booking (Task 34.4, 34.6)
        print("Step 2: Orchestrating Multi-Leg Booking...")
        init_res = await service.initiate_hub_booking(user_id, s)
        assert init_res["success"] is True
        journey_group_id = init_res["journey_group_id"]
        assert "HUB-" in journey_group_id
        assert len(init_res["booking_ids"]) == 2
        print(f"[OK] Multi-leg journey linked under Group: {journey_group_id}")

        # 3. AI Destination Guarantee (Task 34.10)
        print("Step 3: Verifying AI Monitoring (Simulated Delay)...")
        # We need the bookings to have the group ID in their details for the check to work
        # initiate_hub_booking already did this.
        monitor_res = await service.ai_destination_guarantee_check(journey_group_id)
        print(f"Monitor Result: {monitor_res}")
        assert monitor_res["status"] == "AT_RISK"
        assert monitor_res["remaining_buffer"] < 60
        print(f"[OK] AI Guarantee detected risk and provided plans: {monitor_res['message']}")

    finally:
        db.close()

    print("=== Task 34 Full Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_34_full())
