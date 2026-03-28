
import pickle
import os

snapshot_path = "backend/snapshots/graph_snapshot_20260330.pkl"
with open(snapshot_path, "rb") as f:
    snapshot = pickle.load(f)

print(f"📦 Snapshot Date: {snapshot.date}")
print(f"🚇 Stops: {len(snapshot.stop_cache)}")
print(f"🚄 Trips: {len(snapshot._trip_id_map)}")
print(f"🛤️ Segments Data Size: {len(snapshot._segments_data) if snapshot._segments_data is not None else 0}")
print(f"🔄 Transfers Data Size: {len(snapshot._transfers_data) if snapshot._transfers_data is not None else 0}")
