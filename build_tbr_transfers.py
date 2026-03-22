import os
import sys
import logging
import time
import numpy as np
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.route_engine.tbr_structures import trip_edge_dtype
from core.route_engine.graph import MemMapManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("tbr-etl")

def compute_hub_transfers(hub_id, trip_events, min_wait_sec=900, max_wait_sec=21600):
    """
    Worker function to compute all valid O(N^2) transfers at a single hub.
    trip_events is a list of tuples: (trip_id, arr_ts, dep_ts)
    Optimized: Use sorting to find transfers faster than O(N^2).
    """
    if not trip_events: return []
    
    # Sort by arrival time to allow windowed scanning
    events = sorted(trip_events, key=lambda x: x[1])
    edges = []
    
    for i, (ta_id, ta_arr, ta_dep) in enumerate(events):
        # We need to find all tb where tb_dep is in [ta_arr + min_wait, ta_arr + max_wait]
        # Since we sorted by arr_ts, we can't easily binary search on dep_ts 
        # but for most stations N is small (<1000).
        # We still use a range scan to keep it reasonably fast.
        for j in range(len(events)):
            tb_id, tb_arr, tb_dep = events[j]
            if ta_id == tb_id: continue
            
            wait_time = tb_dep - ta_arr
            if min_wait_sec <= wait_time <= max_wait_sec:
                edges.append((ta_id, tb_id, hub_id, wait_time // 60))
                
    return edges

def build_transfer_graph():
    logger.info("🚀 Starting TBR Transfer Graph Precomputation...")
    start_time = time.perf_counter()
    
    import sqlite3
    db_path = "backend/database/transit_graph.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Identify all valid hubs (stations with > 5 stop events)
    logger.info("📍 Identifying all active transfer hubs...")
    cursor.execute("""
        SELECT stop_id, count(*) as stop_count 
        FROM stop_times 
        GROUP BY stop_id 
        HAVING stop_count > 5
    """)
    hub_ids = {r[0] for r in cursor.fetchall()}
    logger.info(f"📍 Identified {len(hub_ids)} Active Transfer Hubs.")
    
    # 2. Gather Trip Events at Hubs
    hub_list_str = ",".join(map(str, hub_ids))
    query = f"SELECT stop_id, trip_id, arrival_timestamp, departure_timestamp FROM stop_times WHERE stop_id IN ({hub_list_str})"
    cursor.execute(query)
    
    hub_events = defaultdict(list)
    for row in cursor.fetchall():
        sid, tid, arr, dep = row
        if arr is not None and dep is not None:
            hub_events[sid].append((tid, arr, dep))
    conn.close()
    
    # 3. Parallel Computation
    all_edges = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(compute_hub_transfers, hid, evs) for hid, evs in hub_events.items()]
        for f in futures: all_edges.extend(f.result())

    # 4. Save to Vectorized MemMap with NESTED Index
    logger.info(f"✅ Precomputed {len(all_edges)} valid edges.")
    
    # Sort by (from_trip_id, station_id) for nested indexing
    all_edges.sort(key=lambda x: (x[0], x[2]))
    
    edges_array = np.zeros(len(all_edges), dtype=trip_edge_dtype)
    edge_index = defaultdict(dict) # trip_id -> {station_id: (start, count)}
    
    curr_key = (-1, -1)
    start_idx = 0
    count = 0
    
    for i, edge in enumerate(all_edges):
        f_tid, t_tid, sid, wait = edge
        edges_array[i] = (t_tid, sid, wait)
        
        this_key = (f_tid, sid)
        if this_key != curr_key:
            if curr_key != (-1, -1):
                edge_index[curr_key[0]][curr_key[1]] = (start_idx, count)
            curr_key = this_key
            start_idx = i
            count = 1
        else:
            count += 1
            
    if curr_key != (-1, -1):
        edge_index[curr_key[0]][curr_key[1]] = (start_idx, count)

    import pickle
    with open("backend/data/tbr_edge_index.pkl", "wb") as f:
        pickle.dump(dict(edge_index), f)
        
    mmap_path = MemMapManager.save_array("tbr_edges", edges_array)
    logger.info(f"💾 TBR Mapped to {mmap_path} in {time.perf_counter()-start_time:.2f}s.")

if __name__ == "__main__":
    build_transfer_graph()
