
import asyncio
from datetime import datetime
import os
import sys
import numpy as np

sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.snapshot_manager import SnapshotManager

async def inspect_bitset():
    manager = SnapshotManager()
    snapshot = await manager.load_snapshot(datetime(2026, 3, 30))
    if not snapshot or snapshot._trip_reachability_bitset is None:
        print("❌ No bitset found.")
        return
    
    # Check SBC (6902) reachability for MAS trips (4736)
    mas_trips = []
    for tid, pid in snapshot._trip_to_pid.items():
         # Manual sequence check
         pos_map = snapshot._trip_stop_pos_map.get(tid, {})
         if 4736 in pos_map:
              mas_trips.append(tid)
    
    print(f"🔎 Found {len(mas_trips)} trips passing through MAS (4736)")
    
    c = 0
    for tid in mas_trips[:10]:
        t_idx = snapshot._trip_id_map.get(tid)
        if t_idx is None: continue
        
        bit_val = snapshot._trip_reachability_bitset[t_idx, 6902 // 64] & (np.uint64(1) << np.uint64(6902 % 64))
        has_sbc = bool(bit_val)
        print(f"🚢 Trip {tid} (idx:{t_idx}) -> SBC(6902) reachable? {has_sbc}")
        if has_sbc: c += 1
    
    print(f"📊 Summary: {c}/10 sample MAS trips reach SBC.")

if __name__ == "__main__":
    asyncio.run(inspect_bitset())
