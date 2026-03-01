import asyncio
import logging
from datetime import datetime, timedelta
from backend.core.route_engine.engine import RailwayRouteEngine
from backend.core.route_engine.constraints import RouteConstraints
from backend.core.route_engine.data_structures import Route, RouteSegment
from backend.database.session import SessionLocal
from backend.database.models import SeatAvailability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_capacity_penalty():
    engine = RailwayRouteEngine()
    
    # Mock some data if needed, but we can just test the scoring function directly
    constraints = RouteConstraints()
    constraints.capacity_weight = 1.0 # Max weight for testing
    
    # travel_date for searching (5 days from now)
    travel_date = datetime.utcnow() + timedelta(days=5)
    
    # Create two routes: one with high availability, one with low
    route_high_avail = Route(
        segments=[
            RouteSegment(
                trip_id=101, train_number="12001",
                departure_stop_id=1, arrival_stop_id=2,
                departure_time=travel_date,
                arrival_time=travel_date + timedelta(hours=2),
                duration_minutes=120, distance_km=100, fare=500
            )
        ],
        total_duration=120,
        total_cost=500
    )
    
    route_low_avail = Route(
        segments=[
            RouteSegment(
                trip_id=102, train_number="12002",
                departure_stop_id=1, arrival_stop_id=2,
                departure_time=travel_date,
                arrival_time=travel_date + timedelta(hours=2),
                duration_minutes=120, distance_km=100, fare=500
            )
        ],
        total_duration=120,
        total_cost=500
    )
    
    session = SessionLocal()
    try:
        # High availability for 12001 (P will be high)
        sa1 = SeatAvailability(
            train_number="12001", class_code="SL", quota="GN",
            availability_status="AVAILABLE-0050", waiting_list_number=0,
            travel_date=travel_date, check_date=datetime.utcnow()
        )
        # Low availability for 12002 (WL 150) (P will be low)
        sa2 = SeatAvailability(
            train_number="12002", class_code="SL", quota="GN",
            availability_status="RLWL/150", waiting_list_number=150,
            travel_date=travel_date, check_date=datetime.utcnow()
        )
        session.add(sa1)
        session.add(sa2)
        session.commit()
        logger.info(f"Seeded availability data for 12001 and 12002")
    finally:
        session.close()

    # Use the raptor engine to score them
    score_high = await engine.raptor._score_with_reliability(route_high_avail, constraints)
    logger.info(f"Route 12001 (Available) Score: {score_high}")
    logger.info(f"P(avail): {route_high_avail.availability_probability}")
    
    score_low = await engine.raptor._score_with_reliability(route_low_avail, constraints)
    logger.info(f"Route 12002 (WL 150) Score: {score_low}")
    logger.info(f"P(avail): {route_low_avail.availability_probability}")
    
    if score_low > score_high:
        logger.info("✅ SUCCESS: Capacity penalty applied correctly!")
        logger.info(f"Penalty difference: {score_low - score_high}")
    else:
        logger.error("❌ FAILURE: Penalty not working as expected.")

if __name__ == "__main__":
    asyncio.run(test_capacity_penalty())
