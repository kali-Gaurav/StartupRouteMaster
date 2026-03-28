import logging
import os
import pickle
import time as _time
import numpy as np
from collections import defaultdict
from typing import Dict, List, Tuple
from .tbr_structures import trip_edge_dtype, tbr_edge_index_dtype
from .graph import MemMapManager

logger = logging.getLogger("tbr_edge_builder")

class TBREdgeBuilder:
    """
    [Task 121: Elite Connectivity] 
    Pre-computes Trip-to-Trip connectivity for O(1) Nexus searches.
    """
    def __init__(self, min_transfer_min: int = 20, max_transfer_min: int = 720):
        self.min_transfer_sec = min_transfer_min * 60
        self.max_transfer_sec = max_transfer_min * 60

    def build_tbr_edges(self, snapshot):
        """
        Compiles the transfer index from trip sequences.
        Ensures tid_1 @ stop_s -> tid_2 @ stop_s if tid_2.dep >= tid_1.arr + buffer.
        """
        logger.info("🚄 TBR: Building Trip-to-Trip Edge Index (Elite Nexus)...")
        start_t = _time.perf_counter()
        
        # 1. Group trips by stop
        stop_to_events = defaultdict(list) # stop_id -> [(arr_ts, dep_ts, tid)]
        
        t_nodes = snapshot.tbr_trip_nodes
        t_index = snapshot.tbr_trip_index
        
        for tid, (off, count) in t_index.items():
            for i in range(count):
                node = t_nodes[off + i]
                # node: (sid, arr_ts, dep_ts)
                stop_to_events[int(node['stop_id'])].append((int(node['arr_ts']), int(node['dep_ts']), tid))
        
        # 2. For each stop, build valid connections
        # We sort by arrival time to optimize the search
        all_edges = []
        # edge_index = {} # trip_id -> {stop_id: (edge_start, edge_count)}
        trip_stop_edges = defaultdict(lambda: defaultdict(list))
        
        logger.info(f"Processing connections for {len(stop_to_events)} stops...")
        
        for sid, events in stop_to_events.items():
            # Sort events by arrival for trip_1 and departure for trip_2
            events.sort() # Sorts by first element (arr_ts)
            
            for i, (arr_1, _, tid_1) in enumerate(events):
                # Search for valid departures after arr_1 + buffer
                target_dep = arr_1 + self.min_transfer_sec
                max_dep = arr_1 + self.max_transfer_sec
                
                # Simple linear scan (we can binary search if too many events per stop)
                # But even for busy stations (500 departures), this is fast.
                for j in range(len(events)):
                    dep_2, _, tid_2 = events[j][1], events[j][0], events[j][2] # Fix: dep_2 is dep_ts, events[j][0] is arr_ts
                    
                    if tid_1 == tid_2: continue # Cannot transfer to the same trip
                    
                    if target_dep <= dep_2 <= max_dep:
                        wait_m = (dep_2 - arr_1) // 60
                        trip_stop_edges[tid_1][sid].append((tid_2, sid, wait_m))
        
        # 3. Flaten into NumPy MemMap for edges and index
        total_edges_count = sum(len(e_list) for s_map in trip_stop_edges.values() for e_list in s_map.values())
        logger.info(f"Generated {total_edges_count} transfer edges.")
        
        np_edges = np.zeros(total_edges_count, dtype=trip_edge_dtype)
        
        # New structure for memmap index: (trip_id, stop_id, offset, count)
        # We need a map from (trip_id, stop_id) to its position in this index array.
        # So we'll first build an intermediate list, then a map, then the array.
        index_entries = []
        # Map (trip_id, stop_id) -> index in index_entries
        index_lookup_map = {}
        
        curr_offset = 0
        current_index_pos = 0
        
        sorted_trip_ids = sorted(trip_stop_edges.keys())
        for tid in sorted_trip_ids:
            sorted_sids = sorted(trip_stop_edges[tid].keys())
            for sid in sorted_sids:
                edge_list = trip_stop_edges[tid][sid]
                count = len(edge_list)
                
                # Store (trip_id, stop_id, offset, count)
                index_entries.append((tid, sid, curr_offset, count))
                index_lookup_map[(tid, sid)] = current_index_pos
                current_index_pos += 1
                
                for k, (to_tid, s_id, wait) in enumerate(edge_list):
                    np_edges[curr_offset + k] = (to_tid, s_id, wait)
                curr_offset += count
        
        np_index = np.zeros(len(index_entries), dtype=tbr_edge_index_dtype)
        for i, entry in enumerate(index_entries):
            np_index[i] = entry
            
        # 4. Save to Disk (Local SSD/Project database)
        from database.config import Config
        data_dir = Config.DATA_DIR
        
        MemMapManager.save_array("tbr_edges", np_edges)
        MemMapManager.save_array("tbr_edge_index", np_index)
        
        # Save the lookup map as pickle temporarily (this can also be vectorized later if needed)
        lookup_map_path = os.path.join(data_dir, "tbr_edge_lookup_map.pkl")
        with open(lookup_map_path, "wb") as f:
            pickle.dump(dict(index_lookup_map), f)
            
        latency = (_time.perf_counter() - start_t) * 1000
        logger.info(f"✅ TBR Edge Index built in {latency:.2f}ms. Edges: {total_edges_count}, Index Entries: {len(index_entries)}. Saved to {data_dir}")
        return total_edges_count
