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
    def __init__(self, timetable_path: str = None):
        self.global_connections = np.array([])
        self.connections = np.array([])
        self.stop_ids = np.array([])
        self.id_to_idx = {}
        self.stop_count = 0
        
        if timetable_path is None:
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

    def find_routes(self, source_stop_id: int, dest_stop_id: int, start_time: int) -> List[Dict]:
        """
        Extracts the full path for the earliest arrival.
        Optimized loop for high-throughput scanning.
        """
        if source_stop_id not in self.id_to_idx or dest_stop_id not in self.id_to_idx:
            return []

        source_idx = self.id_to_idx[source_stop_id]
        dest_idx = self.id_to_idx[dest_stop_id]

        # earliest_arrival[stop_idx] = arrival_time
        earliest_arrival = np.full(self.stop_count, 2147483647, dtype=np.int32)
        earliest_arrival[source_idx] = start_time
        
        # in_connection[stop_idx] = connection_index that brought us here
        in_connection = np.full(self.stop_count, -1, dtype=np.int32)
        trip_reachable = {}

        # CORE CSA SCAN
        for i, c in enumerate(self.connections):
            # 1. Start-time pruning
            if c[2] < start_time: continue
            
            dep_stop, arr_stop, dep_time, arr_time, trip_id = c
            
            # 2. Check reachability
            if earliest_arrival[dep_stop] <= dep_time or trip_reachable.get(trip_id, False):
                # 3. Update arrival
                if arr_time < earliest_arrival[arr_stop]:
                    earliest_arrival[arr_stop] = arr_time
                    in_connection[arr_stop] = i
                    trip_reachable[trip_id] = True
            
            # 4. Global pruning (If we can't arrive earlier than current best at dest)
            if dep_time > earliest_arrival[dest_idx]:
                break

        if earliest_arrival[dest_idx] == 2147483647:
            return []

        # Backtrack
        path = []
        curr_stop = dest_idx
        while curr_stop != source_idx:
            c_idx = in_connection[curr_stop]
            if c_idx == -1: break
            
            conn = self.connections[c_idx]
            path.append({
                "dep_stop": self.stop_ids[conn[0]],
                "arr_stop": self.stop_ids[conn[1]],
                "dep_time": int(conn[2]),
                "arr_time": int(conn[3]),
                "trip_id": int(conn[4])
            })
            curr_stop = conn[0]
            
        return path[::-1]
