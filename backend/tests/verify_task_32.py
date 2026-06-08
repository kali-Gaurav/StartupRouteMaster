import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.route_engine.categorization import CategorizationEngine
from core.data_utils.structures import Route, RouteSegment, Persona

def verify_task_32_complete():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 32 (TOP 3 HIGHLIGHTING)")
    
    # 1. Setup Test Data
    # Route A: Lightning Fast (Lowest duration)
    ra = Route(score=50, total_duration=100, total_cost=1000, availability_probability=0.7)
    ra.add_segment(RouteSegment(trip_id=1, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=100, distance_km=100, train_number="FAST_101"))
    
    # Route B: Best Value (Lowest cost)
    rb = Route(score=60, total_duration=500, total_cost=200, availability_probability=0.7)
    rb.add_segment(RouteSegment(trip_id=2, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=500, distance_km=100, train_number="CHEAP_202"))
    
    # Route C: Most Reliable (Highest Avail)
    rc = Route(score=70, total_duration=300, total_cost=800, availability_probability=0.98)
    rc.add_segment(RouteSegment(trip_id=3, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=300, distance_km=100, train_number="RELY_303"))
    
    # Route D: Generic Budget Choice
    rd = Route(score=80, total_duration=400, total_cost=400, availability_probability=0.6)
    rd.add_segment(RouteSegment(trip_id=4, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=400, distance_km=100, train_number="NORM_404"))

    routes = [ra, rb, rc, rd]

    # 2. Verify BUDGET Persona
    print("\n  Testing BUDGET Persona:")
    res_budget = CategorizationEngine.categorize(routes, Persona.BUDGET)
    highlights = res_budget["top_3_highlight"]
    
    assert len(highlights) == 3
    labels = [h["highlight_label"] for h in highlights]
    reasons = [h["highlight_reason"] for h in highlights]
    
    print(f"    Labels: {labels}")
    print(f"    Reasons: {reasons}")
    
    # Check if specific heuristics triggered
    assert any("Lightning Fast" in l for l in labels)
    assert any("Best Value" in l for l in labels)
    assert any("Most Reliable" in l for l in labels)
    
    # 3. Verify EMERGENCY Persona (Time Priority)
    print("\n  Testing EMERGENCY Persona:")
    # For emergency, we expect the fastest route to be #1
    res_em = CategorizationEngine.categorize(routes, Persona.EMERGENCY)
    em_top = res_em["top_3_highlight"][0]
    print(f"    Top Highlight: {em_top['highlight_label']} | Reason: {em_top['highlight_reason']}")
    assert "Lightning Fast" in em_top["highlight_label"]

    # 4. Verify COMFORT Persona
    print("\n  Testing COMFORT Persona:")
    res_comfort = CategorizationEngine.categorize(routes, Persona.COMFORT)
    comfort_labels = [h["highlight_label"] for h in res_comfort["top_3_highlight"]]
    print(f"    Labels: {comfort_labels}")
    # One of them might be "Maximum Comfort" if not lightning fast or best value
    
    # 5. Check Diversity (Subtask 32.3)
    # Add a duplicate train with slightly worse score
    ra_dup = Route(score=55, total_duration=100, total_cost=1000, availability_probability=0.7)
    ra_dup.add_segment(RouteSegment(trip_id=5, departure_stop_id=1, arrival_stop_id=2, departure_time=datetime.now(), arrival_time=datetime.now(), duration_minutes=100, distance_km=100, train_number="FAST_101"))
    
    res_div = CategorizationEngine.categorize(routes + [ra_dup], Persona.BUDGET)
    div_trains = [h["segments"][0]["train_number"] for h in res_div["top_3_highlight"]]
    print(f"\n  Diversity Check Trains: {div_trains}")
    assert len(set(div_trains)) == 3 # Should still be 3 unique trains
    
    print("\n✅ TASK 32 FULLY VERIFIED")

if __name__ == "__main__":
    verify_task_32_complete()
