from core.route_engine.categorization import CategorizationEngine
from core.data_utils.structures import Route, RouteSegment, Persona
from datetime import datetime

def verify_subtask_32_4():
    print(">>> Verifying Subtask 32.4: Intelligent Tagging")
    
    # 1. Create specialized routes
    # Lightning Fast
    r_fast = Route(score=100, total_duration=50, total_cost=1000, availability_probability=0.5)
    r_fast.add_segment(RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=50, distance_km=100, train_number="FAST1"))
    
    # Best Value (Cheapest)
    r_cheap = Route(score=110, total_duration=200, total_cost=200, availability_probability=0.5)
    r_cheap.add_segment(RouteSegment(trip_id=2, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=200, distance_km=100, train_number="CHEAP1"))
    
    # Most Reliable (High Availability)
    r_reliable = Route(score=120, total_duration=150, total_cost=800, availability_probability=0.95)
    r_reliable.add_segment(RouteSegment(trip_id=3, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=150, distance_km=100, train_number="REL1"))
    
    # 2. Categorize
    res = CategorizationEngine.categorize([r_fast, r_cheap, r_reliable], Persona.BUDGET)
    
    top_3 = res["top_3_highlight"]
    
    # Map labels by train number for easy check
    labels = {t["segments"][0]["train_number"]: t["highlight_label"] for t in top_3}
    print(f"  Assigned labels: {labels}")
    
    assert "⚡ Lightning Fast" in labels["FAST1"]
    assert "💰 Best Value" in labels["CHEAP1"]
    assert "✅ Most Reliable" in labels["REL1"]
    
    # Check is_featured flag
    for t in top_3:
        assert t["is_featured"] == True
    
    print("✅ SUBTASK 32.4 VERIFIED")

if __name__ == "__main__":
    verify_subtask_32_4()
