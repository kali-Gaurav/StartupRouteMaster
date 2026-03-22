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
    """
    if not trip_events: return []
    
    # Sort by arrival time to allow windowed scanning
    events = sorted(trip_events, key=lambda x: x[1])
    edges = []
    
    for i, (ta_id, ta_arr, ta_dep) in enumerate(events):
        # [Issue 10] Pruning: Only keep soonest per next trip, and cap total outgoing
        found_next_trips = set()
        count = 0
        for j in range(len(events)):
            tb_id, tb_arr, tb_dep = events[j]
            if ta_id == tb_id or tb_id in found_next_trips: continue
            
            wait_time = tb_dep - ta_arr
            if min_wait_sec <= wait_time <= max_wait_sec:
                edges.append((ta_id, tb_id, hub_id, wait_time // 60))
                found_next_trips.add(tb_id)
                count += 1
                if count >= 30: break # Cap promising outgoing
                
    return edges

def compute_metro_transfers(group_name, group_events, min_wait_sec=5400, max_wait_sec=28800):
    """
    Compute transfers between DIFFERENT stations in the same metro group.
    """
    edges = []
    sids = list(group_events.keys())
    
    for i, (s1) in enumerate(sids):
        for s2 in sids:
            if s1 == s2: continue 
            s2_events = sorted(group_events[s2], key=lambda x: x[2])
            for tid1, arr1, dep1 in group_events[s1]:
                # [Issue 10] Metro pruning: even stricter as metro groups are huge
                count = 0
                for tid2, arr2, dep2 in s2_events:
                    wait = dep2 - arr1
                    if min_wait_sec <= wait <= max_wait_sec:
                        edges.append((tid1, tid2, s2, wait // 60))
                        count += 1
                        if count >= 10: break # Strictly cap metro inter-station transfers
    return edges

def build_transfer_graph():
    logger.info("🚀 Starting TBR Transfer Graph Precomputation...")
    start_time = time.perf_counter()
    
    import sqlite3
    db_path = "backend/database/transit_graph.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Map Metro Groups [Task 27.15]
    from utils.station_utils import METRO_GROUPS
    
    logger.info("📍 Identifying all active transfer hubs...")
    cursor.execute("SELECT id, code FROM stops")
    all_stops = {r['code']: r['id'] for r in cursor.fetchall()}
    
    cursor.execute("""
        SELECT stop_id, count(*) as stop_count 
        FROM stop_times 
        GROUP BY stop_id 
        HAVING stop_count > 5
    """)
    hub_ids = {r[0] for r in cursor.fetchall()}
    
    metro_stop_map = {}
    metro_group_events = defaultdict(lambda: defaultdict(list))
    
    for gname, codes in METRO_GROUPS.items():
        for code in codes:
            sid = all_stops.get(code)
            if sid:
                metro_stop_map[sid] = gname
                hub_ids.add(sid)
    
    # 2. Gather Trip Events at Hubs
    hub_list_str = ",".join(map(str, hub_ids))
    query = f"SELECT stop_id, trip_id, arrival_timestamp, departure_timestamp FROM stop_times WHERE stop_id IN ({hub_list_str})"
    cursor.execute(query)
    
    hub_events = defaultdict(list)
    for row in cursor.fetchall():
        sid, tid, arr, dep = row['stop_id'], row['trip_id'], row['arrival_timestamp'], row['departure_timestamp']
        if arr is not None and dep is not None:
            hub_events[sid].append((tid, arr, dep))
            if sid in metro_stop_map:
                metro_group_events[metro_stop_map[sid]][sid].append((tid, arr, dep))
    conn.close()
    
    # 3. Parallel Computation
    all_edges = []
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        hub_futures = [executor.submit(compute_hub_transfers, hid, evs) for hid, evs in hub_events.items()]
        metro_futures = [executor.submit(compute_metro_transfers, gname, gevs) for gname, gevs in metro_group_events.items()]
        
        logger.info(f"⚙️ Computing transfers for {len(hub_futures)} hubs and {len(metro_futures)} metro groups...")
        
        for f in hub_futures: all_edges.extend(f.result())
        for f in metro_futures: all_edges.extend(f.result())

    # 4. Save to Vectorized MemMap
    logger.info(f"✅ Precomputed {len(all_edges)} valid edges.")
    all_edges.sort(key=lambda x: (x[0], x[2]))
    
    edges_array = np.zeros(len(all_edges), dtype=trip_edge_dtype)
    edge_index = defaultdict(dict)
    
    curr_key = (-1, -1)
    start_idx = 0
    count = 0
    
    for i, edge in enumerate(all_edges):
        f_tid, t_tid, sid, wait = edge
        edges_array[i] = (t_tid, sid, wait)
        this_key = (f_tid, sid)
        if this_key != curr_key:
            if curr_key != (-1, -1): edge_index[curr_key[0]][curr_key[1]] = (start_idx, count)
            curr_key = this_key; start_idx = i; count = 1
        else: count += 1
            
    if curr_key != (-1, -1): edge_index[curr_key[0]][curr_key[1]] = (start_idx, count)
    
    import pickle
    data_dir = "backend/data"
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "tbr_edge_index.pkl"), "wb") as f:
        pickle.dump(dict(edge_index), f)
        
    mmap_path = MemMapManager.save_array("tbr_edges", edges_array)
    logger.info(f"💾 TBR Mapped to {mmap_path} in {time.perf_counter()-start_time:.2f}s.")

if __name__ == "__main__":
    build_transfer_graph()
