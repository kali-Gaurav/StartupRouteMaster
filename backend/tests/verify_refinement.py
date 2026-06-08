import sys
import os
import math
from datetime import datetime

# Add backend to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from core.data_utils.structures import Route, RouteSegment, Persona
    from core.route_engine.raptor import SearchRoute
    from core.route_engine.tbr_router import haversine
    print("✅ Basic Imports Successful")
except ImportError as e:
    print(f"❌ Import Failure: {e}")
    sys.exit(1)

def verify_raptor_bloom():
    print("Testing RAPTOR 128-bit Bloom Filter...")
    # Create a SearchRoute and add station IDs
    sr = SearchRoute(trip_id=1, from_stop_id=10, to_stop_id=20, 
                     departure_time=datetime.now(), arrival_time=datetime.now(), 
                     round_num=0)
    
    # Low bit (10 % 128 = 10)
    sr.to_stop_id = 10
    sr.add_to_bloom(10)
    # High bit (74 % 128 = 74 -> 74-64 = 10)
    # To test and confirm it's not a false positive, we should have a parent that started/ended at 74
    sr.parent = SearchRoute(trip_id=2, from_stop_id=74, to_stop_id=80,
                            departure_time=datetime.now(), arrival_time=datetime.now(),
                            round_num=0)
    sr.add_to_bloom(74)
    
    assert sr.has_cycle(10) == True, "Should detect ID 10 (low bit)"
    assert sr.has_cycle(74) == True, "Should detect ID 74 (high bit)"
    assert sr.has_cycle(5) == False, "Should not detect ID 5"
    
    # Collision test (ID 138 % 128 = 10)
    # Bloom will hit, but linked list check should prevent false positive
    print(f"Collision test: ID 138 (Bloom hit expected, but has_cycle should be False)")
    assert sr.has_cycle(138) == False, "Linked list check should prevent collision false positive"
    print("✅ RAPTOR Bloom Filter Verified")

def verify_haversine():
    # Delhi to Mumbai approx 1150km
    d = haversine(28.6139, 77.2090, 19.0760, 72.8777)
    print(f"Distance Delhi-Mumbai: {d:.2f} km")
    assert 1100 < d < 1200, "Haversine calculation looks wrong"
    print("✅ Haversine Calculation Verified")

if __name__ == "__main__":
    try:
        verify_raptor_bloom()
        verify_haversine()
        print("\n✨ ALL REFINEMENTS VERIFIED MANUALLY ✨")
    except Exception as e:
        print(f"❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
