import pytest
import asyncio
from datetime import datetime, timedelta
from core.data_structures import Route, RouteSegment, Persona, Passenger, TransferConnection
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import RoutingRequest
from core.route_engine.constraints import RouteConstraints, DiscoveryModel
from database.session import SessionTransit, initialize_database_pools
from database.models import Stop
from core.route_engine.scoring import RouteScorer

@pytest.mark.asyncio
async def test_interlining_rail_flight_stitching():
    """
    Test Case: Aligarh (ALJN) -> Bangalore (SBC).
    Scenario: Train ALJN -> NDLS (Delhi), then Flight DEL -> BLR.
    Verification: InterliningEngine should stitch these.
    """
    await initialize_database_pools()
    with SessionTransit() as db:
        # 1. Mock a rail route from ALJN to NDLS
        rail_route = Route()
        rail_segment = RouteSegment(
            train_number="12301",
            train_name="Aligarh Exp",
            departure_code="ALJN",
            arrival_code="NDLS",
            departure_time=datetime.now().replace(hour=8, minute=0) + timedelta(days=2),
            arrival_time=datetime.now().replace(hour=10, minute=0) + timedelta(days=2),
            travel_class="SL",
            fare=200.0,
            departure_stop_id=1,
            arrival_stop_id=2
        )
        rail_route.add_segment(rail_segment)
        rail_route.metadata["mode"] = "RAIL"
        
        # 2. Mock a flight route from DEL to BLR
        flight_route = Route()
        flight_segment = RouteSegment(
            train_number="SKY-123",
            train_name="SkyMaster Flight",
            departure_code="DEL",
            arrival_code="BLR",
            departure_time=datetime.now().replace(hour=14, minute=0) + timedelta(days=2),
            arrival_time=datetime.now().replace(hour=17, minute=0) + timedelta(days=2),
            travel_class="ECONOMY",
            fare=4500.0,
            departure_stop_id=3,
            arrival_stop_id=4
        )
        flight_route.add_segment(flight_segment)
        flight_route.metadata["mode"] = "FLIGHT"
        
        # 3. Test the InterliningEngine directly
        from core.route_engine.interlining_engine import interlining_engine
        
        interlined = await interlining_engine.find_interlined_routes([rail_route], [flight_route])
        
        print(f"\nFound {len(interlined)} interlined routes.")
        
        for r in interlined:
            modes = r.metadata.get("modes", [])
            print(f"Interlined Route: {' -> '.join([s.departure_code for s in r.segments])} -> {r.segments[-1].arrival_code} (Modes: {modes})")
            assert "FLIGHT" in modes
            assert "RAIL" in modes
            # Check timing
            wait = (r.segments[1].departure_time - r.segments[0].arrival_time).total_seconds() / 3600
            print(f"Wait time at NDLS/DEL: {wait} hours")
            assert 3 <= wait <= 10 # InterliningEngine default window for air is 3-10h

@pytest.mark.asyncio
async def test_arbitrage_release_valve():
    """
    Test Case: High Pressure Rail -> Suggest Alternative.
    """
    await initialize_database_pools()
    from services.agents.arbitrage_agent import arbitrage_agent
    
    source = "NDLS"
    destination = "BOM"
    travel_date = datetime.now() + timedelta(days=1)
    
    alts = await arbitrage_agent.find_arbitrage_routes(source, destination, travel_date)
    
    assert len(alts) > 0
    assert alts[0].metadata.get("mode") in ["BUS", "FLIGHT"]
    print(f"\nArbitrage found: {alts[0].segments[0].train_name} costing {alts[0].total_cost}")

@pytest.mark.asyncio
async def test_safety_scoring_solo_female():
    """
    Test Case: Night transfer safety penalty for solo female passenger.
    """
    await initialize_database_pools()
    
    # Create a route with a night transfer
    route = Route()
    seg1 = RouteSegment(
        departure_code="S1", arrival_code="S2",
        departure_time=datetime.now().replace(hour=20, minute=0),
        arrival_time=datetime.now().replace(hour=23, minute=45) # Night arrival
    )
    seg2 = RouteSegment(
        departure_code="S2", arrival_code="S3",
        departure_time=datetime.now().replace(hour=2, minute=0) + timedelta(days=1), # Night departure
        arrival_time=datetime.now().replace(hour=8, minute=0) + timedelta(days=1)
    )
    route.add_segment(seg1)
    route.add_segment(seg2)
    
    # Add transfer with all required fields
    tc = TransferConnection(
        station_id=101,
        station_code="S2",
        arrival_time=seg1.arrival_time,
        departure_time=seg2.departure_time,
        duration_minutes=135,
        station_name="Test Hub",
        facilities_score=4.0,
        safety_score=3.5,
        platform_from="1",
        platform_to="2",
        is_multi_station=False,
        transfer_type="WALK"
    )
    route.add_transfer(tc)
    
    constraints = RouteConstraints(persona=Persona.COMFORT)
    
    # 1. Score for generic passenger
    score_generic = await RouteScorer.score_route(route, constraints, passengers=[Passenger(gender="M")])
    
    # 2. Score for solo female passenger
    score_female = await RouteScorer.score_route(route, constraints, passengers=[Passenger(gender="F")])
    
    print(f"\nSafety Scoring Test:")
    print(f"Generic Score: {score_generic}")
    print(f"Solo Female Score: {score_female}")
    
    # Solo female should have a higher (worse) score due to night transfer penalty
    assert score_female > score_generic
    
    # Verify the penalty amount (expected 2000 for night transfer)
    diff = score_female - score_generic
    print(f"Penalty Difference: {diff}")
    assert diff >= 2000

if __name__ == "__main__":
    asyncio.run(test_interlining_rail_flight_stitching())
    asyncio.run(test_arbitrage_release_valve())
    asyncio.run(test_safety_scoring_solo_female())
