from core.pricing.fare_calculator import calculate_fare
from core.route_engine.scoring import RouteScorer
from core.route_engine.constraints import RouteConstraints
from core.data_utils.structures import Route, RouteSegment, Persona, Passenger
from datetime import datetime

async def verify_task_39():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 39 (PASSENGER PERSONAS)")
    
    distance = 1000.0
    coach = "3A"
    
    # 1. Test Multi-Passenger Fare (Subtask 39.5)
    # 1 Adult (30), 1 Senior (65), 1 Infant (3)
    passengers = [
        {"age": 30},
        {"age": 65},
        {"age": 3}
    ]
    fare_res = calculate_fare(distance, coach, passengers=passengers)
    print(f"  Fare for [Adult, Senior, Infant]: ₹{fare_res['total_fare']}")
    
    # Senior gets 40% off base, Infant is free
    # Expect fare to be around 1.6x of single adult base
    fare_single = calculate_fare(distance, coach, passengers=[{"age": 30}])
    print(f"  Fare for [Single Adult]: ₹{fare_single['total_fare']}")
    assert fare_res['total_fare'] < fare_single['total_fare'] * 2
    
    # 2. Test Persona-Aware Scoring (Subtask 39.2)
    from core.data_utils.structures import TransferConnection
    r_transfer = Route(total_duration=500, total_cost=1000)
    r_transfer.add_segment(RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=200, distance_km=100))
    r_transfer.add_transfer(TransferConnection(station_id=2, station_name="HUB", arrival_time=datetime.now(), departure_time=datetime.now(), duration_minutes=100))
    r_transfer.add_segment(RouteSegment(trip_id=2, departure_stop_id=2, arrival_stop_id=3, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=200, distance_km=100))
    
    c = RouteConstraints(persona=Persona.COMFORT)
    
    # Score for Adult vs Senior
    p_adult = [Passenger(age=30)]
    p_senior = [Passenger(age=70)]
    
    score_adult = await RouteScorer.score_route(r_transfer, c, passengers=p_adult)
    score_senior = await RouteScorer.score_route(r_transfer, c, passengers=p_senior)
    
    print(f"  Score (Adult): {score_adult:.1f}")
    print(f"  Score (Senior): {score_senior:.1f}")
    
    # Senior should have a higher (worse) score for a route with transfers
    assert score_senior > score_adult
    
    print("\n✅ TASK 39 FULLY VERIFIED")

if __name__ == "__main__":
    import asyncio
    asyncio.run(verify_task_39())
