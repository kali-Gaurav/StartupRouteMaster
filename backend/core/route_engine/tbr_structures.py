"""
Trip-Based Routing (TBR) Core Data Structures
Optimized for high-speed, memory-efficient graph traversal.
"""

import numpy as np

class TripNode:
    """
    Represents a single stop event within a continuous Trip sequence.
    Using __slots__ prevents the creation of a __dict__ for each instance,
    saving significant memory when millions of these nodes are loaded.
    """
    __slots__ = ('stop_id', 'arrival_time', 'departure_time')
    
    def __init__(self, stop_id: int, arrival_time: int, departure_time: int):
        self.stop_id = stop_id
        self.arrival_time = arrival_time
        self.departure_time = departure_time

    def __repr__(self):
        return f"TripNode(stop={self.stop_id}, arr={self.arrival_time}, dep={self.departure_time})"

class TripEdge:
    """
    Represents a valid physical transfer connection from the current trip 
    to a new trip at a specific station.
    """
    __slots__ = ('to_trip_id', 'station_id', 'wait_time_mins')
    
    def __init__(self, to_trip_id: int, station_id: int, wait_time_mins: int):
        self.to_trip_id = to_trip_id
        self.station_id = station_id
        self.wait_time_mins = wait_time_mins

    def __repr__(self):
        return f"TripEdge(to_trip={self.to_trip_id} @ stop={self.station_id}, wait={self.wait_time_mins}m)"

# =============================================================================
# ULTIMATE PERFORMANCE TIER: NumPy Structured Arrays
# Eliminates Python object overhead entirely. 
# =============================================================================

# 10 bytes per node. 10M nodes = 100MB.
# stop_id: Max 65,535 (Currently ~8,500 stops)
# arr_ts / dep_ts: Seconds since midnight or epoch modulo (uint32 max is ~136 years)
trip_node_dtype = np.dtype([
    ('stop_id', np.uint16),
    ('arr_ts', np.uint32),
    ('dep_ts', np.uint32)
])

# 8 bytes per edge. 10M edges = 80MB.
# to_trip_id: Max 4.2 billion trips
# station_id: Max 65,535
# wait_time_mins: Max 65,535 mins (~45 days)
trip_edge_dtype = np.dtype([
    ('to_trip_id', np.uint32),
    ('station_id', np.uint16),
    ('wait_time_mins', np.uint16)
])
