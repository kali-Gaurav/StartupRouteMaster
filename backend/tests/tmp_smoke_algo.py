from core.route_engine import TimeDependentGraph, Route, RouteSegment, TransferConnection, OptimizedRAPTOR
from datetime import datetime

def make_segment(trip_id, dep_stop, arr_stop, dep_time=None, arr_time=None, distance=10.0):
    dep_time = dep_time or datetime(2026, 2, 19, 8, 0)
    arr_time = arr_time or datetime(2026, 2, 19, 9, 0)
    return RouteSegment(
        trip_id=trip_id,
        departure_stop_id=dep_stop,
        arrival_stop_id=arr_stop,
        departure_time=dep_time,
        arrival_time=arr_time,
        duration_minutes=int((arr_time - dep_time).total_seconds() // 60),
        distance_km=distance,
        fare=50.0
    )

# bitset smoke
g = TimeDependentGraph()
g.stop_cache = {10: None, 20: None, 30: None}
g.build_stop_index()
bits = g.stations_to_bitset([10,30])
assert isinstance(bits, int) and bits != 0
r = Route(); r.segments = [make_segment(1,10,20), make_segment(1,20,30)]
rb = g.route_to_bitset(r)
assert rb & bits == bits
print('✓ bitset helpers smoke OK')

# transfer cache smoke
g2 = TimeDependentGraph()
t = TransferConnection(station_id=20, arrival_time=datetime.now(), departure_time=datetime.now(), duration_minutes=10, station_name='S', facilities_score=0.8, safety_score=0.9)
g2.add_transfer(10, t)
assert len(g2.get_transfer_between_stops(10,20))==1
print('✓ transfer cache smoke OK')

# pattern indexing smoke
engine = OptimizedRAPTOR()
g3 = TimeDependentGraph()
g3.stop_cache = {1: None,2:None,3:None}
segs = [make_segment(100,1,2), make_segment(100,2,3)]
g3.trip_segments[100] = segs
key = g3.pattern_for_trip(100)
assert isinstance(key, tuple)
g3.route_patterns[key] = [100]
# monkeypatch engine._build_graph to return our graph
engine._build_graph = lambda date: g3
trips = engine.find_trips_by_stop_sequence([1,2,3])
print('find_trips_by_stop_sequence returns (deferred coroutine):', trips)
print('✓ pattern indexing smoke OK')

# dominance pruning smoke
engine2 = OptimizedRAPTOR()
g4 = TimeDependentGraph(); g4.stop_cache={1:None,2:None,3:None}; g4.build_stop_index()
r1 = Route(); r1.segments=[make_segment(1,1,2)]; r1.total_duration=100; r1.total_cost=100; r1.transfers=[]; r1.reliability=0.9; r1.score=100
r2 = Route(); r2.segments=[make_segment(2,1,2)]; r2.total_duration=120; r2.total_cost=90; r2.transfers=[]; r2.reliability=0.85; r2.score=110
r3 = Route(); r3.segments=[make_segment(3,1,3)]; r3.total_duration=95; r3.total_cost=110; r3.transfers=[TransferConnection(2, datetime.now(), datetime.now(), 10, 'X', 0.7, 0.9)]; r3.reliability=0.92; r3.score=95
kept = __import__('asyncio').get_event_loop().run_until_complete(engine2._deduplicate_routes([r1,r2,r3], g4))
assert r2 not in kept
print('✓ dominance pruning smoke OK')
