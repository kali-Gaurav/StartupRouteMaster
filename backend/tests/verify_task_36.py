from core.route_engine.scoring import RouteScorer
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Route, RouteSegment, Persona
from datetime import datetime

async def verify_task_36():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 36 (RISK ZONE WARNINGS)")
    
    # 1. Create a route passing through high-risk stations (CNB, ALD, MGS)
    r = Route(total_duration=600, total_cost=1000, availability_probability=0.9)
    r.add_segment(RouteSegment(
        trip_id=1, departure_stop_id=1, arrival_stop_id=2, 
        departure_time=datetime.now(), arrival_time=datetime.now(), 
        duration_minutes=200, distance_km=200, departure_code="NDLS", arrival_code="CNB"
    ))
    r.add_segment(RouteSegment(
        trip_id=1, departure_stop_id=2, arrival_stop_id=3, 
        departure_time=datetime.now(), arrival_time=datetime.now(), 
        duration_minutes=200, distance_km=200, departure_code="CNB", arrival_code="PRYJ"
    ))
    r.add_segment(RouteSegment(
        trip_id=1, departure_stop_id=3, arrival_stop_id=4, 
        departure_time=datetime.now(), arrival_time=datetime.now(), 
        duration_minutes=200, distance_km=200, departure_code="PRYJ", arrival_code="DDU"
    ))
    
    c = RouteConstraints(persona=Persona.COMFORT)
    
    # 2. Score it
    await RouteScorer.score_route(r, c)
    
    print(f"  Risk Level: {r.metadata['breakdown'].get('risk_level')}")
    print(f"  Risk Warnings: {r.metadata.get('risk_warnings')}")
    
    # Check for high risk (3+ stations hit: CNB, PRYJ, DDU are in our list)
    assert r.metadata['breakdown'].get('risk_level') == "HIGH"
    assert len(r.metadata.get('risk_warnings')) > 0
    assert "Frequent heavy delays" in r.metadata['risk_warnings'][0]
    
    print("\n✅ TASK 36 FULLY VERIFIED")

if __name__ == "__main__":
    import asyncio
    asyncio.run(verify_task_36())
