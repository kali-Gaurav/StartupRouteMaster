import numpy as np
import logging
import os
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class CSARoutingKernel:
    """
    UPGRADED Subtask 3.6: High-performance CSA kernel.
    Supports dynamic injection of stitched multi-zonal connection data.
    """
    def __init__(self, timetable_path: Optional[str] = None):
        self.global_connections = np.array([])
        self.connections = np.array([])
        self.stop_ids = np.array([])
        self.id_to_idx = {}
        self.stop_count = 0
        
        if not timetable_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            timetable_path = os.path.normpath(os.path.join(base_dir, "..", "..", "data", "timetable.npz"))
            
        self._load_global_data(timetable_path)

    def _load_global_data(self, path: str):
        try:
            logger.info(f"Loading Global CSA timetable from {path}")
            data = np.load(path)
            self.global_connections = data['connections']
            self.connections = self.global_connections
            self.stop_ids = data['stop_ids']
            self.stop_count = len(self.stop_ids)
            self.id_to_idx = {sid: i for i, sid in enumerate(self.stop_ids)}
        except Exception as e:
            logger.error(f"Failed to load global timetable: {e}")

    def inject_stitched_data(self, stitched_connections: np.ndarray):
        """
        JIT Injection: Replaces the current search space with stitched zonal data.
        """
        # Ensure data is sorted by departure time (Required for CSA)
        # connections: [dep_stop_idx, arr_stop_idx, dep_ts, arr_ts, trip_id]
        self.connections = stitched_connections[stitched_connections[:, 2].argsort()]
        logger.debug(f"💉 JIT: Injected {len(self.connections)} connections into Kernel.")

    def reset_to_global(self):
        """Reverts search space to the full global graph."""
        self.connections = self.global_connections

    def find_routes(self, source_stop_id: int, dest_stop_id: int, start_time: int) -> List[List[Dict]]:
        """
        UPGRADED: Returns multiple Pareto-optimal paths.
        Dimensions: [Arrival Time, Number of Transfers]
        """
        if source_stop_id not in self.id_to_idx or dest_stop_id not in self.id_to_idx:
            return []

        source_idx = self.id_to_idx[source_stop_id]
        dest_idx = self.id_to_idx[dest_stop_id]

        # multi_earliest_arrival[stop_idx][num_transfers] = arrival_time
        MAX_TRANSFERS = 3
        earliest_arrival = np.full((self.stop_count, MAX_TRANSFERS + 1), 2147483647, dtype=np.int32)
        earliest_arrival[source_idx, 0] = start_time
        
        # in_connection[stop_idx][num_transfers] = connection_index
        in_connection = np.full((self.stop_count, MAX_TRANSFERS + 1), -1, dtype=np.int32)
        
        # track trip reachability per transfer count
        trip_reachable = np.full((len(self.connections), MAX_TRANSFERS + 1), False, dtype=bool)

        # CORE CSA SCAN
        for i, c in enumerate(self.connections):
            dep_time = c[2]
            if dep_time < start_time: continue
            
            dep_stop, arr_stop, arr_time, trip_id = int(c[0]), int(c[1]), int(c[3]), int(c[4])
            
            for t in range(MAX_TRANSFERS + 1):
                # 1. Stay on same trip (no extra transfer)
                # 2. Start new trip from a stop reached in t-1 transfers
                can_reach = False
                if earliest_arrival[dep_stop, t] <= dep_time:
                    can_reach = True
                elif t > 0 and earliest_arrival[dep_stop, t-1] <= dep_time:
                    can_reach = True
                
                if can_reach:
                    if arr_time < earliest_arrival[arr_stop, t]:
                        # Pruning: only update if this is better than any lower-transfer arrival
                        is_pareto = True
                        for prev_t in range(t):
                            if earliest_arrival[arr_stop, prev_t] <= arr_time:
                                is_pareto = False
                                break
                        
                        if is_pareto:
                            earliest_arrival[arr_stop, t] = arr_time
                            in_connection[arr_stop, t] = i

        # Extract all Pareto-optimal paths to destination
        results = []
        best_overall_arrival = 2147483647
        
        for t in range(MAX_TRANSFERS + 1):
            arr_t = earliest_arrival[dest_idx, t]
            if arr_t < 2147483647 and arr_t < best_overall_arrival:
                # Backtrack this specific (dest, t) Pareto point
                path = []
                curr_stop = dest_idx
                curr_t = t
                while curr_stop != source_idx:
                    c_idx = in_connection[curr_stop, curr_t]
                    if c_idx == -1: break
                    
                    conn = self.connections[c_idx]
                    path.append({
                        "dep_stop": self.stop_ids[int(conn[0])],
                        "arr_stop": self.stop_ids[int(conn[1])],
                        "dep_time": int(conn[2]),
                        "arr_time": int(conn[3]),
                        "trip_id": int(conn[4])
                    })
                    
                    # Did we transfer to get to this trip?
                    prev_stop = int(conn[0])
                    # If we couldn't have reached dep_stop at dep_time with curr_t transfers, 
                    # it must have been curr_t - 1.
                    if curr_t > 0 and earliest_arrival[prev_stop, curr_t] > conn[2]:
                        curr_t -= 1
                    
                    curr_stop = prev_stop
                
                if path:
                    results.append(path[::-1])
                
                best_overall_arrival = arr_t # In CSA, higher t must have earlier arrival to be Pareto

        return results
