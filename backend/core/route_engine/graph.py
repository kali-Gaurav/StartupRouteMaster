from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Optional, Set
from collections import defaultdict
import logging

from database.models import Stop


from .data_structures import RouteSegment, TransferConnection, Route

logger = logging.getLogger(__name__)

@dataclass
class StaticGraphSnapshot:
    """Pre-built static graph snapshot (Schedule-based)"""
    date: datetime
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
    
    version: str = "v2.5"
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
    def get_departures_from_stop(self, stop_id: int, after_time: datetime, lookahead_minutes: int = 1440) -> List[Tuple[datetime, int]]:
        """Get departures from stop after given time, considering real-time delays and cancellations.
        Uses binary search for O(log N) lookup efficiency.
        """
        if after_time >= datetime(3000, 1, 1): # Safety check for datetime.max
            return []
            
        base_departures = self.departures_by_stop.get(stop_id, [])
        if not base_departures:
            return []

        # Find the insertion point for after_time (using dummy trip_id -1 for comparison)
        idx = bisect_left(base_departures, (after_time, -1))
        candidates = base_departures[idx:]

        # Apply Real-time Overlay (Phase 2: COW Layer)
        adjusted = []
        try:
            limit_time = after_time + timedelta(minutes=lookahead_minutes)
        except OverflowError:
            limit_time = datetime.max
        
        for dt, trip_id in candidates:
            # Since base_departures is sorted by time, we can break once dt exceeds limit
            if dt > limit_time:
                break
                
            if self.overlay.is_cancelled(trip_id):
                continue
            
            delay = self.overlay.get_trip_delay(trip_id)
            try:
                effective_time = dt + timedelta(minutes=delay)
            except OverflowError:
                effective_time = datetime.max
            
            # Check after delay adjustment (might have shifted earlier or later)
            if after_time <= effective_time <= limit_time:
                adjusted.append((effective_time, trip_id))

        return sorted(adjusted, key=lambda x: x[0])

    def get_transfers_from_stop(self, stop_id: int, arrival_time: datetime,
                               min_transfer_time: int = 15) -> List[TransferConnection]:
        """Get feasible transfers from stop, honoring real-time state."""
        transfers = self.transfer_graph.get(stop_id, [])
        feasible = []

        for transfer in transfers:
            # We assume the TransferConnection object represents a window and we check feasibility against it.
            # Use a safe check for the 'infinite' window (datetime.min to datetime.max)
            is_in_window = False
            if transfer.arrival_time == datetime.min and transfer.departure_time == datetime.max:
                is_in_window = True
            else:
                is_in_window = (transfer.arrival_time <= arrival_time <= transfer.departure_time)

            if is_in_window:
                # Calculate duration in minutes correctly using total_seconds()
                if transfer.departure_time == datetime.max:
                    # For infinite windows (same-station), any duration is fine as long as it's >= min
                    duration_min = min_transfer_time + 1
                else:
                    duration_min = int((transfer.departure_time - arrival_time).total_seconds() / 60)
                
                # Check if we have enough time to make the transfer
                # Max transfer window: 24 hours (1440 mins) for production stability
                if min_transfer_time <= duration_min <= 1440:
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
