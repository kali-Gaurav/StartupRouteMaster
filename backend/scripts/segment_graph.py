import numpy as np
import os
from pathlib import Path

DATA_DIR = Path("backend/data")
SEGMENTS_DIR = DATA_DIR / "graph_segments"
SEGMENTS_DIR.mkdir(exist_ok=True)

def segment_graph():
    print("🚀 Segmenting Routing Graph...")
    data = np.load(DATA_DIR / "timetable.npz")
    connections = data['connections']
    stop_ids = data['stop_ids']
    
    # 1. Group connections into 10 zones based on departure stop_id
    num_zones = 10
    max_stop = connections[:, 0].max()
    zone_size = (max_stop // num_zones) + 1
    
    for zone_id in range(num_zones):
        start_id = zone_id * zone_size
        end_id = (zone_id + 1) * zone_size
        
        # Filter connections where departure stop is in this zone
        mask = (connections[:, 0] >= start_id) & (connections[:, 0] < end_id)
        zone_conns = connections[mask]
        
        if len(zone_conns) > 0:
            filename = SEGMENTS_DIR / f"zone_{zone_id}.npz"
            np.savez_compressed(filename, connections=zone_conns)
            print(f"✅ Saved Zone {zone_id}: {len(zone_conns)} connections")
        else:
            print(f"⚠️ Zone {zone_id} is empty, skipping.")

    print("🏁 Graph segmentation complete.")

if __name__ == "__main__":
    segment_graph()
