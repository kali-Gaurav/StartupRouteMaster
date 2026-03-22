
import asyncio
import logging
from datetime import datetime, date
import sys
import os
import numpy as np

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("raptor-debug-sync")

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.engine import route_engine

async def debug_graph_sync():
    print("--- RAPTOR GRAPH SYNC DEBUG ---")
    
    # 1. Initialize
    await container.get('db')
    await container.get('search')
    
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    graph = await route_engine._get_current_graph(departure_date)
    snap = graph.snapshot
    
    print(f"Snapshot Date: {snap.date}")
    print(f"Total Stops in Map: {len(snap._stop_id_map)}")
    print(f"Total Trips in Map: {len(snap._trip_id_map)}")
    
    # NDLS ID check
    ndls_id = 5533
    ndls_idx = snap._stop_id_map.get(ndls_id)
    print(f"NDLS (5533) Index: {ndls_idx}")
    
    if ndls_idx is not None:
        start, count = snap._pattern_deps_index[ndls_idx]
        print(f"Pattern departures from NDLS: {count}")
        if count > 0:
            sample = snap._pattern_deps_data[start]
            print(f"Sample departure: PID={sample[0]}, TS={sample[1]}, TID={sample[2]}")
            
            # Check if this TID exists in segments map
            trip_id = sample[2]
            trip_idx = snap._trip_id_map.get(trip_id)
            print(f"Trip {trip_id} Index in segments: {trip_idx}")
            
            if trip_idx is not None:
                s_start, s_count = snap._segments_index[trip_idx]
                print(f"Segments for trip {trip_id}: {s_count}")
                if s_count > 0:
                    seg_sample = snap._segments_data[s_start]
                    print(f"Sample Segment: {seg_sample}")
                    # [trip_id, dep_stop, arr_stop, dep_ts, arr_ts, dist_m, service_mask]
                    print(f"  Dep Stop ID: {seg_sample[1]}")
                    print(f"  Dep Timestamp: {seg_sample[3]}")
                    print(f"  Weekday Bitmask: {seg_sample[6]}")

    await container.shutdown()

if __name__ == "__main__":
    asyncio.run(debug_graph_sync())
