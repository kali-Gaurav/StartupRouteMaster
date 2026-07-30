import logging
import os
import pickle
import time as _time
import bisect
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
        stop_to_events = defaultdict(list)  # stop_id -> [(arr_ts, dep_ts, tid)]
        
        t_nodes = snapshot.tbr_trip_nodes
        t_index = snapshot.tbr_trip_index
        
        for tid, (off, count) in t_index.items():
            for i in range(count):
                node = t_nodes[off + i]
                stop_to_events[int(node['stop_id'])].append(
                    (int(node['arr_ts']), int(node['dep_ts']), tid)
                )
        
        # 2. For each stop, build valid connections using bisect for O(N log N)
        trip_stop_edges = defaultdict(lambda: defaultdict(list))
        
        logger.info(f"Processing connections for {len(stop_to_events)} stops...")
        
        for sid, events in stop_to_events.items():
            events.sort()  # Sort by arr_ts (first element)
            
            # Build a sorted list of departure times for bisect lookup
            dep_sorted = sorted(events, key=lambda x: x[1])
            dep_times = [e[1] for e in dep_sorted]
            
            for arr_1, _, tid_1 in events:
                target_dep = arr_1 + self.min_transfer_sec
                max_dep = arr_1 + self.max_transfer_sec
                
                # O(log N) bisect to find first valid departure
                lo = bisect.bisect_left(dep_times, target_dep)
                
                for j in range(lo, len(dep_sorted)):
                    dep_2 = dep_sorted[j][1]
                    if dep_2 > max_dep:
                        break  # All further departures are too late
                    
                    tid_2 = dep_sorted[j][2]
                    if tid_1 == tid_2:
                        continue  # Cannot transfer to the same trip
                    
                    wait_m = (dep_2 - arr_1) // 60
                    trip_stop_edges[tid_1][sid].append((tid_2, sid, wait_m))
        
        # 3. Flatten into NumPy MemMap for edges and index
        total_edges_count = sum(
            len(e_list)
            for s_map in trip_stop_edges.values()
            for e_list in s_map.values()
        )
        logger.info(f"Generated {total_edges_count} transfer edges.")
        
        np_edges = np.zeros(total_edges_count, dtype=trip_edge_dtype)
        
        index_entries = []
        # Map (trip_id, stop_id) -> index in index_entries
        index_lookup_map = {}
        # [P0 FIX] Secondary map: trip_id -> {stop_id: index_pos}
        # Enables O(1) "which stops on this trip have outgoing transfers?" lookups
        trip_to_stops_map = defaultdict(dict)
        
        curr_offset = 0
        current_index_pos = 0
        
        sorted_trip_ids = sorted(trip_stop_edges.keys())
        for tid in sorted_trip_ids:
            sorted_sids = sorted(trip_stop_edges[tid].keys())
            for sid in sorted_sids:
                edge_list = trip_stop_edges[tid][sid]
                count = len(edge_list)
                
                index_entries.append((tid, sid, curr_offset, count))
                index_lookup_map[(tid, sid)] = current_index_pos
                trip_to_stops_map[tid][sid] = current_index_pos
                current_index_pos += 1
                
                for k, (to_tid, s_id, wait) in enumerate(edge_list):
                    np_edges[curr_offset + k] = (to_tid, s_id, wait)
                curr_offset += count
        
        np_index = np.zeros(len(index_entries), dtype=tbr_edge_index_dtype)
        for i, entry in enumerate(index_entries):
            np_index[i] = entry
            
        # 4. Save to Disk
        from database.config import Config
        data_dir = Config.DATA_DIR
        
        MemMapManager.save_array("tbr_edges", np_edges)
        MemMapManager.save_array("tbr_edge_index", np_index)
        
        # Save tuple-keyed lookup map (for exact (trip, stop) -> index lookups)
        lookup_map_path = os.path.join(data_dir, "tbr_edge_lookup_map.pkl")
        with open(lookup_map_path, "wb") as f:
            pickle.dump(dict(index_lookup_map), f)
        
        # [P0 FIX] Save per-trip transfer stops map (for "which stops have transfers?" lookups)
        trip_stops_map_path = os.path.join(data_dir, "tbr_trip_to_stops_map.pkl")
        with open(trip_stops_map_path, "wb") as f:
            pickle.dump(dict(trip_to_stops_map), f)
            
        latency = (_time.perf_counter() - start_t) * 1000
        logger.info(
            f"✅ TBR Edge Index built in {latency:.2f}ms. "
            f"Edges: {total_edges_count}, Index Entries: {len(index_entries)}, "
            f"Trips with transfers: {len(trip_to_stops_map)}. Saved to {data_dir}"
        )
        return total_edges_count
