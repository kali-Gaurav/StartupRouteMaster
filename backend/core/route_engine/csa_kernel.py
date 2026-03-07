import numpy as np
import logging
import os
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class CSARoutingKernel:
    """
    High-performance Connection Scan Algorithm (CSA) kernel.
    Scans a sorted NumPy array of connections in O(C) time.
    """
    def __init__(self, timetable_path: str = None):
        if timetable_path is None:
            # Task 7: Robust Path Resolution
            base_dir = os.path.dirname(os.path.abspath(__file__))
            timetable_path = os.path.normpath(os.path.join(base_dir, "..", "..", "data", "timetable.npz"))
            
        try:
            logger.info(f"Loading CSA timetable from {timetable_path}")
            data = np.load(timetable_path)
            self.connections = data['connections']
            self.stop_ids = data['stop_ids']
            self.stop_count = len(self.stop_ids)
            # Map stop_id to internal index
            self.id_to_idx = {sid: i for i, sid in enumerate(self.stop_ids)}
        except Exception as e:
            logger.error(f"Failed to load timetable: {e}")
            self.connections = np.array([])
            self.stop_ids = np.array([])
            self.stop_count = 0

    def find_earliest_arrival(self, source_stop_id: int, dest_stop_id: int, start_time: int) -> Optional[int]:
        """
        Classic CSA: Finds the earliest possible arrival time at dest from source.
        """
        if source_stop_id not in self.id_to_idx or dest_stop_id not in self.id_to_idx:
            return None

        source_idx = self.id_to_idx[source_stop_id]
        dest_idx = self.id_to_idx[dest_stop_id]

        # earliest_arrival[stop_idx] = arrival_time
        earliest_arrival = np.full(self.stop_count, 2147483647, dtype=np.int32) # MAX_INT
        earliest_arrival[source_idx] = start_time

        # trip_reachable[trip_id] = True if we can board this trip
        # For simplicity, we assume trip_id is unique across days in the compiled data
        # or we use a dictionary if trip_ids are sparse.
        trip_reachable = {}

        # Scan connections sorted by departure time
        # connections: [dep_stop_idx, arr_stop_idx, dep_ts, arr_ts, trip_id]
        for c in self.connections:
            # Skip connections departing before our start_time
            if c[2] < start_time:
                continue

            dep_stop, arr_stop, dep_time, arr_time, trip_id = c
            
            # Can we board? 
            # 1. We reached the departure stop before the train leaves
            # 2. We are already on this trip
            if earliest_arrival[dep_stop] <= dep_time or trip_reachable.get(trip_id, False):
                # Update arrival at destination stop
                if arr_time < earliest_arrival[arr_stop]:
                    earliest_arrival[arr_stop] = arr_time
                    trip_reachable[trip_id] = True

            # Optimization: If we already found an arrival at dest earlier than current connection departure, 
            # we can't do better with any LATER connection (since they are sorted by departure).
            # Wait, that's only true if there are no transfers. With transfers, we still need to scan.
            # But we can prune if dep_time > earliest_arrival[dest_idx].
            if dep_time > earliest_arrival[dest_idx]:
                break

        result = earliest_arrival[dest_idx]
        return result if result < 2147483647 else None

    def find_routes(self, source_stop_id: int, dest_stop_id: int, start_time: int) -> List[Dict]:
        """
        Extracts the full path for the earliest arrival.
        """
        if source_stop_id not in self.id_to_idx or dest_stop_id not in self.id_to_idx:
            return []

        source_idx = self.id_to_idx[source_stop_id]
        dest_idx = self.id_to_idx[dest_stop_id]

        earliest_arrival = np.full(self.stop_count, 2147483647, dtype=np.int32)
        earliest_arrival[source_idx] = start_time
        
        # in_connection[stop_idx] = connection_index that brought us here
        in_connection = np.full(self.stop_count, -1, dtype=np.int32)
        trip_reachable = {}

        for i, c in enumerate(self.connections):
            if c[2] < start_time: continue
            
            dep_stop, arr_stop, dep_time, arr_time, trip_id = c
            
            if earliest_arrival[dep_stop] <= dep_time or trip_reachable.get(trip_id, False):
                if arr_time < earliest_arrival[arr_stop]:
                    earliest_arrival[arr_stop] = arr_time
                    in_connection[arr_stop] = i
                    trip_reachable[trip_id] = True
            
            if dep_time > earliest_arrival[dest_idx]:
                break

        if earliest_arrival[dest_idx] == 2147483647:
            return []

        # Backtrack to find the path
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
