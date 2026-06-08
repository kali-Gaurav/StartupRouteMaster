from core.route_engine.scoring import RouteScorer
from core.route_engine.constraints import RouteConstraints
from core.data_utils.structures import Route, RouteSegment, Persona
from datetime import datetime

async def verify_task_34():
    print("\n>>> VERIFYING TASK 34: METADATA ENRICHMENT")
    
    # 1. Create a high-quality route
    r = Route(total_duration=120, total_cost=500, availability_probability=0.95)
    # Direct
    r.add_segment(RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=120, distance_km=100, has_pantry=True))
    
    c = RouteConstraints(persona=Persona.BUDGET)
    
    # 2. Score it
    await RouteScorer.score_route(r, c)
    
    print(f"  Breakdown: {r.metadata.get('breakdown')}")
    print(f"  UI Reasons: {r.metadata.get('ui_reasons')}")
    
    # Check for enrichment
    assert "reliability_label" in r.metadata["breakdown"]
    assert len(r.metadata["ui_reasons"]) > 0
    assert "Direct journey" in r.metadata["ui_reasons"]
    assert "Pantry car available" in r.metadata["ui_reasons"]
    
    print("✅ TASK 34 VERIFIED: Rich metadata injected into route.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(verify_task_34())
