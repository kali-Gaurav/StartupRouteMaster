import sys, os
sys.path.append(os.getcwd())

from backend.core.route_engine.graph import StaticGraphSnapshot
from backend.core.route_engine.raptor import RouteSegment
from backend.database import SessionLocal
from datetime import datetime

# load latest snapshot
import pickle
snapshot_path = 'snapshots/graph_snapshot_20260325.pkl'
with open(snapshot_path,'rb') as f:
    snap = pickle.load(f)

# try to access trip segments for trip_id 2073 earlier maybe
trip_id = 2073
segments = snap.trip_segments.get(trip_id)
print('segments count', len(segments))
if segments:
    total_dist = sum(s.distance_km for s in segments)
    total_fare = sum(s.fare for s in segments)
    print('total distance', total_dist, 'total fare', total_fare)
    for s in segments[:10]:
        print(s)
