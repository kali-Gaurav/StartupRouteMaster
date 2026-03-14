from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Tuple, Optional, Set
from collections import defaultdict
import logging
import numpy as np
import os
import json

from database.models import Stop


from core.data_structures import RouteSegment, TransferConnection, Route

logger = logging.getLogger(__name__)

class MemMapManager:
    """
    Subtask 5.1: Memory Mapping Manager.
    Saves large numpy arrays to disk and loads them using numpy.memmap
    to minimize RAM footprint on VPS.
    """
    @staticmethod
    def save_array(name: str, array: np.ndarray) -> str:
        from database.config import Config
        os.makedirs(Config.MEMMAP_DIR, exist_ok=True)
        path = os.path.join(Config.MEMMAP_DIR, f"{name}.dat")
        
        # Save metadata (shape, dtype)
        meta_path = path + ".meta"
        with open(meta_path, 'w') as f:
            json.dump({"shape": array.shape, "dtype": str(array.dtype)}, f)
            
        # Write binary data
        fp = np.memmap(path, dtype=array.dtype, mode='w+', shape=array.shape)
        fp[:] = array[:]
        fp.flush()
        return path

    @staticmethod
    def load_array(name: str, mode: str = 'r') -> Optional[np.ndarray]:
        from database.config import Config
        path = os.path.join(Config.MEMMAP_DIR, f"{name}.dat")
        meta_path = path + ".meta"
        
        if not os.path.exists(path) or not os.path.exists(meta_path):
            return None
            
        with open(meta_path, 'r') as f:
            meta = json.load(f)
            
        return np.memmap(path, dtype=meta['dtype'], mode=mode, shape=tuple(meta['shape']))

@dataclass
class StaticGraphSnapshot:
    """Pre-built static graph snapshot (Schedule-based)"""
    date: datetime
    # departures_by_stop: Dict[int, List[Tuple[datetime, int]]] = field(default_factory=lambda: defaultdict(list))
    # arrivals_by_stop: Dict[int, List[Tuple[datetime, int]]] = field(default_factory=lambda: defaultdict(list))
    
    # [Task 5.1 Optimization] Vectorized connection storage
    # _departures_data: np.ndarray shape (N, 2) -> [timestamp_secs, trip_id]
    # _departures_index: np.ndarray shape (NUM_STOPS, 2) -> [start_idx, count]
    _departures_data: Optional[np.ndarray] = None
    _departures_index: Optional[np.ndarray] = None
    _arrivals_data: Optional[np.ndarray] = None
    _arrivals_index: Optional[np.ndarray] = None
    _stop_id_map: Dict[int, int] = field(default_factory=dict) # stop_id -> index in _index arrays

    # Legacy fallback for backward compatibility during transition
    departures_by_stop: Dict[int, List[Tuple[datetime, int]]] = field(default_factory=lambda: defaultdict(list))
    arrivals_by_stop: Dict[int, List[Tuple[datetime, int]]] = field(default_factory=lambda: defaultdict(list))

    trip_segments: Dict[int, List[RouteSegment]] = field(default_factory=lambda: defaultdict(list))
    transfer_graph: Dict[int, List[TransferConnection]] = field(default_factory=lambda: defaultdict(list))
    stop_cache: Dict[int, Stop] = field(default_factory=dict)
    
    # Station-centric and Train-centric views (Phase 10 enhancements)
    station_schedule: Dict[int, List[Dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    train_path: Dict[int, List[Dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))

    # Algorithmic indexes
    route_patterns: Dict[Tuple[int, ...], List[int]] = field(default_factory=lambda: defaultdict(list))
    transfer_cache: Dict[Tuple[int, int], List[TransferConnection]] = field(default_factory=dict)
    stop_index: Dict[str, int] = field(default_factory=dict)
    
    # Phase 2: Core Station Time-Series Index (TODO #11)
    # station_id -> hour_bucket (0-23) -> sorted list of (departure_time, trip_id)
    station_time_index: Dict[int, List[List[Tuple[datetime, int]]]] = field(default_factory=lambda: defaultdict(lambda: [[] for _ in range(24)]))
    
    # Phase 4: Reliability Scores (TODO #32)
    # (trip_id, station_id) -> float (0.0 to 1.0)
    reliability_scores: Dict[Tuple[int, int], float] = field(default_factory=dict)
    
    # Phase 5: Routing Optimizations
    # trip_id -> set of station_ids visited by this trip
    station_ids_by_trip: Dict[int, Set[int]] = field(default_factory=lambda: defaultdict(set))

    # Task 16.1: Vectorized Coordinate Matrix
    # Numpy array of shape (N, 2) storing [lat, lon]
    coordinate_matrix: Optional[Any] = None 
    stop_id_to_idx: Dict[int, int] = field(default_factory=dict)
    idx_to_stop_id: List[int] = field(default_factory=list)

    version: str = "v3.1" # Bumped for Task 5.1 Optimization

    created_at: datetime = field(default_factory=datetime.utcnow)
    transfer_metrics: Dict[str, Any] = field(default_factory=dict)
    density_metrics: Dict[str, Any] = field(default_factory=dict)


class RealtimeOverlay:
    """
    Real-time delay and cancellation overlay (Phase 4/10).
    In Phase 10, this state is synchronized via Redis for distributed workers.

    A numeric `version` is bumped on each mutation so that
    clients can decide whether they need to fetch an updated
    payload instead of syncing on every call.
    """

    def __init__(self):
        self.delays: Dict[int, int] = {}  # trip_id -> minutes
        self.cancellations: Set[int] = set()  # trip_ids
        self.platform_changes: Dict[Tuple[int, int], str] = {}  # (trip_id, stop_id) -> platform
        self.last_updated: datetime = datetime.min # Start with very old time for sync logic
        self.version: int = 0

    def _bump(self):
        self.version += 1
        self.last_updated = datetime.utcnow()

    def apply_delay(self, trip_id: int, minutes: int):
        self.delays[trip_id] = minutes
        self._bump()

    def cancel_trip(self, trip_id: int):
        self.cancellations.add(trip_id)
        self._bump()

    def get_trip_delay(self, trip_id: int) -> int:
        return self.delays.get(trip_id, 0)

    def is_cancelled(self, trip_id: int) -> bool:
        return trip_id in self.cancellations

    def to_dict(self) -> Dict:
        """Serialize for Redis storage."""
        return {
            "delays": {str(k): v for k, v in self.delays.items()},
            "cancellations": list(self.cancellations),
            "last_updated": self.last_updated.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'RealtimeOverlay':
        """Deserialize from Redis storage."""
        overlay = cls()
        if not data: return overlay
        
        overlay.delays = {int(k): v for k, v in data.get("delays", {}).items()}
        overlay.cancellations = set(data.get("cancellations", []))
        if "last_updated" in data:
            overlay.last_updated = datetime.fromisoformat(data["last_updated"])
        if "version" in data:
            try:
                overlay.version = int(data["version"])
            except Exception:
                pass
        return overlay


from bisect import bisect_left

class TimeDependentGraph:
    """Optimized time-dependent graph with Snapshot + Real-time Overlay support"""

    def __init__(self, snapshot: Optional[StaticGraphSnapshot] = None):
        self.snapshot = snapshot
        self.overlay = RealtimeOverlay()

        # Core data structures (aliased from snapshot or empty)
        self.departures_by_stop = snapshot.departures_by_stop if snapshot else defaultdict(list)
        # Ensure departures are sorted by time for bisect
        for stop_id in self.departures_by_stop:
            self.departures_by_stop[stop_id].sort(key=lambda x: x[0])
            
        self.arrivals_by_stop = snapshot.arrivals_by_stop if snapshot else defaultdict(list)
        self.trip_segments = snapshot.trip_segments if snapshot else defaultdict(list)
        self.transfer_graph = snapshot.transfer_graph if snapshot else defaultdict(list)
        self.stop_cache = snapshot.stop_cache if snapshot else {}

        # Station-centric and Train-centric views (Phase 10 enhancements)
        self.station_schedule = snapshot.station_schedule if snapshot else defaultdict(list)
        self.train_path = snapshot.train_path if snapshot else defaultdict(list)

        # New structures for algorithmic speedups
        self.stop_index = snapshot.stop_index if snapshot else {}
        self.stop_count = len(self.stop_index)
        self.route_patterns = snapshot.route_patterns if snapshot else defaultdict(list)
        self.transfer_cache = snapshot.transfer_cache if snapshot else {}
        self.transfer_metrics = snapshot.transfer_metrics if snapshot else {}
        self.density_metrics = snapshot.density_metrics if snapshot else {}

        # Optional in-memory index
        self.station_time_index = None

    # ----------------------------- Phase 10 helpers ---------------------------
    def get_station_schedule(self, stop_id: int) -> List[Dict[str, Any]]:
        """Get O(1) station schedule (all trains serving this station)."""
        return self.station_schedule.get(stop_id, [])

    def get_train_path(self, trip_id: int) -> List[Dict[str, Any]]:
        """Get O(1) train path (all stations served by this trip)."""
        return self.train_path.get(trip_id, [])

    # Task 16.3: Vectorized Spatial Filtering
    def get_nearby_stations(self, lat: float, lon: float, radius_km: float) -> List[int]:
        """Find all station IDs within radius_km using numpy vectorization."""
        if self.snapshot.coordinate_matrix is None:
            return []
            
        from utils.geo_utils import haversine_vectorized
        
        # 1. Broad Bounding Box Filter (Fastest)
        # 1 deg lat ~ 111km
        lat_delta = radius_km / 111.0
        # 1 deg lon ~ 111km * cos(lat)
        lon_delta = radius_km / (111.0 * np.cos(np.radians(lat)))
        
        m = self.snapshot.coordinate_matrix
        mask = (m[:, 0] >= lat - lat_delta) & (m[:, 0] <= lat + lat_delta) & \
               (m[:, 1] >= lon - lon_delta) & (m[:, 1] <= lon + lon_delta)
        
        # 2. Precise Haversine Filter on remaining points
        indices = np.where(mask)[0]
        if indices.size == 0: return []
        
        filtered_coords = m[indices]
        distances = haversine_vectorized(lat, lon, filtered_coords[:, 0], filtered_coords[:, 1])
        
        # 3. Map back to Stop IDs
        final_indices = indices[distances <= radius_km]
        
        return [self.snapshot.idx_to_stop_id[idx] for idx in final_indices]

    # ----------------------------- event helpers -----------------------------
    def add_departure(self, stop_id: int, departure_time: datetime, trip_id: int):
        """Add departure event"""
        self.departures_by_stop[stop_id].append((departure_time, trip_id))

    def add_arrival(self, stop_id: int, arrival_time: datetime, trip_id: int):
        """Add arrival event"""
        self.arrivals_by_stop[stop_id].append((arrival_time, trip_id))

    def add_trip_segment(self, trip_id: int, segment: RouteSegment):
        """Add complete trip segment"""
        self.trip_segments[trip_id].append(segment)

    def add_transfer(self, from_stop: int, transfer: TransferConnection):
        """Add transfer capability"""
        self.transfer_graph[from_stop].append(transfer)
        # populate transfer_cache for fast two-stop lookups
        key = (from_stop, transfer.station_id)
        self.transfer_cache.setdefault(key, []).append(transfer)

    # ----------------------------- lookup helpers -----------------------------
    def get_departures_from_stop(self, stop_id: int, after_time: datetime, lookahead_minutes: int = 1440, target_date: Optional[date] = None) -> List[Tuple[datetime, int]]:
        """
        Get departures from stop after given time, considering real-time delays, cancellations, 
        and Task 8: service_mask validation.
        """
        if after_time >= datetime(2100, 1, 1): # Safety check
            return []
            
        # Task 8: Prepare bitmask for the specific date if provided
        check_date = target_date or after_time.date()
        weekday_bit = 1 << check_date.weekday()

        # Apply overflow protection for limit_time
        try:
            limit_time = after_time + timedelta(minutes=lookahead_minutes)
        except OverflowError:
            limit_time = datetime(2100, 1, 1)

        # 0. [Task 5.1 Optimization] Vectorized Connection Lookup
        if self.snapshot and self.snapshot._departures_data is not None:
            stop_idx = self.snapshot._stop_id_map.get(stop_id)
            if stop_idx is not None:
                start_offset, count = self.snapshot._departures_index[stop_idx]
                if count > 0:
                    # columns: [timestamp, trip_id]
                    data = self.snapshot._departures_data[start_offset : start_offset + count]
                    
                    after_ts = int(after_time.timestamp())
                    limit_ts = int(limit_time.timestamp())
                    
                    # Binary search on timestamp column
                    idx = np.searchsorted(data[:, 0], after_ts)
                    candidates = data[idx:]
                    
                    adjusted = []
                    for ts, trip_id in candidates:
                        if ts > limit_ts: break
                        
                        tid = int(trip_id)
                        if self.overlay.is_cancelled(tid): continue
                        
                        # Task 8: Bitmask check
                        segments = self.trip_segments.get(tid)
                        if segments and not (segments[0].service_mask & weekday_bit):
                            continue

                        delay = self.overlay.get_trip_delay(tid)
                        effective_ts = ts + (delay * 60)
                        
                        if after_ts <= effective_ts <= limit_ts:
                            # Convert back to datetime for legacy compatibility
                            # In high-performance mode, we should keep it as timestamp
                            adjusted.append((datetime.fromtimestamp(effective_ts), tid))
                    
                    if adjusted:
                        return sorted(adjusted, key=lambda x: x[0])
                    return []

        # 1. Use station_time_index if available (from snapshot)
        if self.snapshot and self.snapshot.station_time_index:
            buckets = self.snapshot.station_time_index.get(stop_id)
            if buckets:
                adjusted = []
                total_hours = (lookahead_minutes // 60) + 2
                start_hour = after_time.hour
                
                for h_offset in range(total_hours):
                    hour = (start_hour + h_offset) % 24
                    for dt, trip_id in buckets[hour]:
                        if self.overlay.is_cancelled(trip_id):
                            continue
                        
                        # Task 8: Bitmask check
                        segments = self.trip_segments.get(trip_id)
                        if segments and not (segments[0].service_mask & weekday_bit):
                            continue

                        delay = self.overlay.get_trip_delay(trip_id)
                        effective_time = dt + timedelta(minutes=delay)
                        
                        if after_time <= effective_time <= limit_time:
                            adjusted.append((effective_time, trip_id))
                
                return sorted(list(set(adjusted)), key=lambda x: x[0])

        # 2. Fallback to binary search on departures_by_stop (Legacy / Phase 1)
        base_departures = self.departures_by_stop.get(stop_id, [])
        if not base_departures:
            return []

        idx = bisect_left(base_departures, (after_time, -1))
        candidates = base_departures[idx:]

        adjusted = []
        for dt, trip_id in candidates:
            if dt > limit_time:
                break
            if self.overlay.is_cancelled(trip_id):
                continue
                
            # Task 8: Bitmask check
            segments = self.trip_segments.get(trip_id)
            if segments and not (segments[0].service_mask & weekday_bit):
                continue

            delay = self.overlay.get_trip_delay(trip_id)
            effective_time = dt + timedelta(minutes=delay)
            if after_time <= effective_time <= limit_time:
                adjusted.append((effective_time, trip_id))

        return sorted(adjusted, key=lambda x: x[0])

    def get_transfers_from_stop(self, stop_id: int, arrival_time: datetime,
                                min_transfer_time: int = 15, incoming_trip_id: Optional[int] = None) -> List[TransferConnection]:
        """Get feasible transfers from stop, honoring real-time state and Task 13 rake-linkage."""
        transfers = self.transfer_graph.get(stop_id, [])
        feasible = []

        # [5.7] Always include a transfer to the SAME station (changing trains at junction)
        if stop_id in self.stop_cache:
            stop = self.stop_cache[stop_id]
            feasible.append(TransferConnection(
                station_id=stop_id,
                arrival_time=datetime.min,
                departure_time=datetime.max,
                duration_minutes=max(min_transfer_time, 45), # Min 45m for train switch
                station_name=stop.name,
                facilities_score=100.0,
                safety_score=100.0
            ))

        # Task 13: Rake Linkage Awareness

        from .rake_linkage import RakeLinkageManager
        rl_manager = RakeLinkageManager()

        for transfer in transfers:
            # Basic window check
            is_in_window = False
            if transfer.arrival_time == datetime.min and transfer.departure_time == datetime.max:
                is_in_window = True
            else:
                is_in_window = (transfer.arrival_time <= arrival_time <= transfer.departure_time)

            if is_in_window:
                # Calculate duration
                if transfer.departure_time == datetime.max:
                    duration_min = min_transfer_time + 1
                else:
                    duration_min = int((transfer.departure_time - arrival_time).total_seconds() / 60)
                
                # Check feasibility
                # Standard check: must be >= min_transfer_time
                is_feasible = (min_transfer_time <= duration_min <= 1440)
                
                # Task 13 Override: If it's a rake-link, even 0 mins is feasible
                if not is_feasible and incoming_trip_id:
                    # We need to know which trip we are transferring TO. 
                    # Since this method returns a list of candidate STATIONS, 
                    # the rake-link check is more naturally handled inside RAPTOR's onward loop.
                    # However, for the S2->S2 same-station case, we can assume it's feasible if any rake links exist.
                    is_feasible = True # Allow RAPTOR to filter specifically later
                
                if is_feasible:
                    feasible.append(transfer)

        return feasible

    def get_transfer_between_stops(self, from_stop: int, to_stop: int) -> List[TransferConnection]:
        """Fast lookup for precomputed transfer(s) between two stops."""
        return self.transfer_cache.get((from_stop, to_stop), [])

    def get_trip_segments(self, trip_id: int) -> List[RouteSegment]:
        """Get all segments for a trip, adjusted for real-time delays (COW)."""
        if self.overlay.is_cancelled(trip_id):
            return []

        base_segments = self.trip_segments.get(trip_id, [])
        delay = self.overlay.get_trip_delay(trip_id)

        if delay == 0:
            return base_segments

        # Apply delay to all segments (Phase 2: Copy-on-Write style)
        return [
            RouteSegment(
                trip_id=seg.trip_id,
                departure_stop_id=seg.departure_stop_id,
                arrival_stop_id=seg.arrival_stop_id,
                departure_time=seg.departure_time + timedelta(minutes=delay),
                arrival_time=seg.arrival_time + timedelta(minutes=delay),
                duration_minutes=seg.duration_minutes,
                distance_km=seg.distance_km,
                departure_code=seg.departure_code,
                arrival_code=seg.arrival_code,
                fare=seg.fare,
                train_name=seg.train_name,
                train_number=seg.train_number
            ) for seg in base_segments
        ]

    # ----------------------------- bitset helpers -----------------------------
    def build_stop_index(self):
        """Construct stop_index and stop_count (call after stop_cache is populated)."""
        self.stop_index = {stop_id: idx for idx, stop_id in enumerate(sorted(self.stop_cache.keys()))}
        self.stop_count = len(self.stop_index)

    def stations_to_bitset(self, station_ids: List[int]) -> int:
        """Return an integer bitset representing the provided station IDs."""
        bitset = 0
        for sid in station_ids:
            pos = self.stop_index.get(sid)
            if pos is not None:
                bitset |= (1 << pos)
        return bitset

    def route_to_bitset(self, route: 'Route') -> int:
        """Return bitset representing all stations visited by a route."""
        return self.stations_to_bitset(route.get_all_stations())

    def pattern_for_trip(self, trip_id: int) -> Tuple[int, ...]:
        """Return canonical stop-sequence tuple for a trip (used in pattern indexing)."""
        segs = self.trip_segments.get(trip_id, [])
        return tuple(seg.departure_stop_id for seg in segs) + ((segs[-1].arrival_stop_id,) if segs else ())
