import sys, os
sys.path.append(os.getcwd())
import pickle
from backend.core.route_engine.graph import StaticGraphSnapshot

path='snapshots/graph_snapshot_20260325.pkl'
with open(path,'rb') as f:
    snap=pickle.load(f)
seg=snap.trip_segments.get(2073,[])
dists=[s.distance_km for s in seg]
print('count',len(dists))
print('max',max(dists) if dists else None)
print('min',min(dists) if dists else None)
print('sum',sum(dists))
print('first10',dists[:10])
print('last10',dists[-10:])
