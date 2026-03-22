"""
Verification script for Task 4: Circular Route Detection (Bloom Filter)
- Ensures that no circular (repeated station) routes are returned by RAPTOR.
- Uses a synthetic graph with intentional cycles to test detection.
"""
import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))
from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.graph import TimeDependentGraph
from core.route_engine.constraints import RouteConstraints

# --- Synthetic Graph Setup ---
class DummyGraph(TimeDependentGraph):
    def __init__(self):
        self.patterns = {
            1: [(datetime.now(), 100)],
            2: [(datetime.now() + timedelta(minutes=5), 200)]
        }
        self.trips = {
            100: [  # Trip 100: 1 -> 2 -> 3 -> 1 (cycle)
                (100, 1, 2, 0, 5*60, 10, 127),
                (100, 2, 3, 5*60, 10*60, 10, 127),
                (100, 3, 1, 10*60, 15*60, 10, 127)
            ],
            200: [  # Trip 200: 1 -> 4 (no cycle)
                (200, 1, 4, 0, 10*60, 10, 127)
            ]
        }
        self.overlay = type('O', (), {'get_trip_delay': lambda self, tid: 0})()
    def get_pattern_departures(self, source_stop_id, departure_dt, lookahead_minutes=1440):
        return self.patterns
    def can_reach_destination(self, trip_id, dest_stop_id):
        return True
    def get_trip_segments_raw(self, trip_id):
        return self.trips.get(trip_id, [])
    def get_transfers_from_stop(self, stop_id, arrival_time, min_transfer_time=15, incoming_trip_id=None):
        return []
    def get_trip_segments(self, trip_id):
        return []

def main():
    graph = DummyGraph()
    raptor = OptimizedRAPTOR()
    constraints = RouteConstraints(max_results=10)
    routes = raptor._search_multi_departure_sync(graph, 1, 4, datetime.now(), constraints, lambda: None)
    print(f"Found {len(routes)} routes.")
    for r in routes:
        path = []
        curr = r
        while curr:
            path.append(curr.to_stop_id)
            curr = curr.parent
        print("Route:", list(reversed(path)))
        assert len(path) == len(set(path)), "Cycle detected in route!"  # No repeated stations
    print("Task 4 verification PASSED: No cycles in any route.")

if __name__ == "__main__":
    main()
