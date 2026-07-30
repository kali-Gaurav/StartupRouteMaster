from core.route_engine.categorization import CategorizationEngine
from core.data_utils.structures import Route, RouteSegment, Persona
from datetime import datetime

def verify_subtask_32_3():
    print(">>> Verifying Subtask 32.3: Diversity Filtering")
    
    # 1. Create 4 routes
    # R1 and R2 are the same train (12625) but different "scores"
    r1 = Route(score=100)
    r1.add_segment(RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=60, distance_km=100, train_number="12625"))
    
    r2 = Route(score=110)
    r2.add_segment(RouteSegment(trip_id=2, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=60, distance_km=100, train_number="12625"))
    
    # R3 is a different train (12626)
    r3 = Route(score=120)
    r3.add_segment(RouteSegment(trip_id=3, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=60, distance_km=100, train_number="12626"))
    
    # R4 is another different train (12627)
    r4 = Route(score=130)
    r4.add_segment(RouteSegment(trip_id=4, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=60, distance_km=100, train_number="12627"))
    
    # 2. Categorize
    res = CategorizationEngine.categorize([r1, r2, r3, r4], Persona.BUDGET)
    
    top_3 = res["top_3_highlight"]
    print(f"  Top 3 highlight count: {len(top_3)}")
    assert len(top_3) == 3
    
    train_numbers = [t["segments"][0]["train_number"] for t in top_3]
    print(f"  Highlighted train numbers: {train_numbers}")
    
    # Should NOT contain duplicate 12625
    assert len(set(train_numbers)) == 3
    assert "12625" in train_numbers
    assert "12626" in train_numbers
    assert "12627" in train_numbers
    
    print("✅ SUBTASK 32.3 VERIFIED")

if __name__ == "__main__":
    verify_subtask_32_3()
