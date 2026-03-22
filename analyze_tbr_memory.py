import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.data_structures import RouteSegment
from core.route_engine.tbr_structures import TripNode
from pympler import asizeof

def main():
    print("--- Memory Footprint Analysis: RouteSegment vs TripNode ---")
    
    # 1. Base Object Size
    seg = RouteSegment(
        trip_id=1, train_number="12345", 
        departure_stop_id=10, arrival_stop_id=20,
        departure_time="10:00:00", arrival_time="12:00:00",
        duration_minutes=120, distance_km=150.0, fare=500.0,
        service_mask=127, is_unconfirmed_allowed=False, has_pantry=False,
        departure_code="SRC", arrival_code="DST", metadata={}
    )
    
    node = TripNode(stop_id=10, arrival_time=36000, departure_time=36300)
    
    # sys.getsizeof only gets the top level pointer size
    print(f"sys.getsizeof(RouteSegment): {sys.getsizeof(seg)} bytes")
    print(f"sys.getsizeof(TripNode): {sys.getsizeof(node)} bytes")
    
    # pympler.asizeof gets deep size including dicts and strings
    try:
        seg_deep = asizeof.asizeof(seg)
        node_deep = asizeof.asizeof(node)
        print(f"\nDeep Size (RouteSegment): {seg_deep} bytes")
        print(f"Deep Size (TripNode): {node_deep} bytes")
        
        ratio = seg_deep / node_deep
        print(f"TripNode is {ratio:.1f}x smaller than RouteSegment.")
        
        # Extrapolate to 10 Million nodes (Typical Indian Railway Graph Scale)
        seg_10m = (seg_deep * 10_000_000) / (1024 * 1024)
        node_10m = (node_deep * 10_000_000) / (1024 * 1024)
        print(f"\nExtrapolated RAM for 10 Million Elements:")
        print(f"  RouteSegments: {seg_10m:.1f} MB")
        print(f"  TripNodes: {node_10m:.1f} MB")
        print(f"  Savings: {seg_10m - node_10m:.1f} MB")
        
    except ImportError:
        print("pympler not installed. Skipping deep size analysis.")

if __name__ == "__main__":
    main()
