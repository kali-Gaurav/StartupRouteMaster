import asyncio
import sys
import os
from datetime import date

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.demand_redistribution_service import (
    DemandRedistributionService, DemandSnapshot
)

async def test_redistribution_engine():
    print("\n--- Testing Redistribution Engine ---")
    
    service = DemandRedistributionService()
    
    # 1. Mock a High Demand Route (Saturated)
    high_demand_route = DemandSnapshot(
        route_id="NDLS-BCT-EXP",
        source="NDLS",
        destination="BCT",
        travel_date=date.today(),
        total_capacity=500,
        current_bookings=480, # 96%
        search_demand=200,
        demand_score=0.95,
        available_seats=20,
        occupancy_rate=0.96
    )
    
    # 2. Mock a Low Demand Route (Available)
    low_demand_route = DemandSnapshot(
        route_id="NDLS-MMCT-SLOW",
        source="NDLS",
        destination="BCT",
        travel_date=date.today(),
        total_capacity=500,
        current_bookings=100, # 20%
        search_demand=50,
        demand_score=0.2,
        available_seats=400,
        occupancy_rate=0.2
    )
    
    # Manually set the network demand
    service._network_demand = {
        high_demand_route.route_id: high_demand_route,
        low_demand_route.route_id: low_demand_route
    }
    
    # 3. Identify Opportunities
    opportunities = await service.identify_opportunities()
    print(f"Opportunities identified: {len(opportunities)}")
    
    assert len(opportunities) > 0, "Should find a redistribution opportunity from high to low demand"
    
    opp = opportunities[0]
    print(f"Opportunity: {opp.source_route.route_id} -> {opp.target_route.route_id}")
    print(f"Passengers needed: {opp.passengers_needed}")
    
    # 4. Check Incentive
    incentive = service._calculate_incentive(opp.source_route, opp.target_route)
    print(f"Calculated Incentive: {incentive} INR")
    
    assert incentive >= service.MIN_INCENTIVE, "Incentive should be at least minimum"
    
    # 5. Generate Offer
    offers = await service.generate_passenger_offers(opp, limit=1)
    assert len(offers) > 0
    print(f"Offer generated: {offers[0].message}")
    
    print("Test Redistribution Logic Passed!")

if __name__ == "__main__":
    asyncio.run(test_redistribution_engine())
