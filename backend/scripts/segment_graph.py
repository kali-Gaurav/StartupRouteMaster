import numpy as np
import os
import json
from pathlib import Path

# Adjusting paths to be relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MMAP_DIR = DATA_DIR / "memmap"
ZONES_DIR = MMAP_DIR / "zones"

os.makedirs(ZONES_DIR, exist_ok=True)

def segment_graph():
    print("🚀 Upgraded Segmenting Routing Graph for MMAP...")
    timetable_path = DATA_DIR / "timetable.npz"
    if not timetable_path.exists():
        print(f"❌ Timetable not found at {timetable_path}. Run compile_timetable.py first.")
        return

    data = np.load(timetable_path)
    connections = data['connections']
    
    # connections columns: [src_idx, dst_idx, dep_ts, arr_ts, trip_id]
    
    # Group into zones based on departure stop ID (using the index in timetable)
    num_zones = 10
    max_stop_idx = connections[:, 0].max()
    zone_size = (max_stop_idx // num_zones) + 1
    
    for zone_id in range(num_zones):
        start_idx = zone_id * zone_size
        end_idx = (zone_id + 1) * zone_size
        
        mask = (connections[:, 0] >= start_idx) & (connections[:, 0] < end_idx)
        zone_conns = connections[mask]
        
        if len(zone_conns) > 0:
            dat_path = ZONES_DIR / f"zone_{zone_id}.dat"
            meta_path = ZONES_DIR / f"zone_{zone_id}.meta"
            
            # Save Metadata
            with open(meta_path, 'w') as f:
                json.dump({
                    "shape": list(zone_conns.shape),
                    "dtype": str(zone_conns.dtype)
                }, f)
            
            # Save Binary Data as MMAP
            fp = np.memmap(dat_path, dtype=zone_conns.dtype, mode='w+', shape=zone_conns.shape)
            fp[:] = zone_conns[:]
            fp.flush()
            
            print(f"✅ Saved Zone {zone_id}: {len(zone_conns)} connections (MMAP)")
        else:
            print(f"⚠️ Zone {zone_id} is empty, skipping.")

    print("🏁 Graph segmentation complete.")

if __name__ == "__main__":
    segment_graph()
