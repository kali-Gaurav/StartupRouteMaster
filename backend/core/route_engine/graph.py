from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
import logging

from ...database.models import Stop
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
    
    # Algorithmic indexes
    route_patterns: Dict[Tuple[int, ...], List[int]] = field(default_factory=lambda: defaultdict(list))
    transfer_cache: Dict[Tuple[int, int], List[TransferConnection]] = field(default_factory=dict)
    stop_index: Dict[str, int] = field(default_factory=dict)
    
    version: str = "v2.0"
    created_at: datetime = field(default_factory=datetime.utcnow)


class RealtimeOverlay:
    """
    Real-time delay and cancellation overlay (Phase 4/10).
    In Phase 10, this state is synchronized via Redis for distributed workers.
    """

    def __init__(self):
        self.delays: Dict[int, int] = {}  # trip_id -> minutes
        self.cancellations: Set[int] = set()  # trip_ids
        self.platform_changes: Dict[Tuple[int, int], str] = {}  # (trip_id, stop_id) -> platform
        self.last_updated: datetime = datetime.min # Start with very old time for sync logic

    def apply_delay(self, trip_id: int, minutes: int):
        self.delays[trip_id] = minutes
        self.last_updated = datetime.utcnow()

    def cancel_trip(self, trip_id: int):
        self.cancellations.add(trip_id)
        self.last_updated = datetime.utcnow()

    def get_trip_delay(self, trip_id: int) -> int:
        return self.delays.get(trip_id, 0)

    def is_cancelled(self, trip_id: int) -> bool:
        return trip_id in self.cancellations

    def to_dict(self) -> Dict:
        """Serialize for Redis storage."""
        return {
            "delays": {str(k): v for k, v in self.delays.items()},
            "cancellations": list(self.cancellations),
            "last_updated": self.last_updated.isoformat()
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
        return overlay


class TimeDependentGraph:
    """Optimized time-dependent graph with Snapshot + Real-time Overlay support"""

    def __init__(self, snapshot: Optional[StaticGraphSnapshot] = None):
        self.snapshot = snapshot
        self.overlay = RealtimeOverlay()

        # Core data structures (aliased from snapshot or empty)
        self.departures_by_stop = snapshot.departures_by_stop if snapshot else defaultdict(list)
        self.arrivals_by_stop = snapshot.arrivals_by_stop if snapshot else defaultdict(list)
        self.trip_segments = snapshot.trip_segments if snapshot else defaultdict(list)
        self.transfer_graph = snapshot.transfer_graph if snapshot else defaultdict(list)
        self.stop_cache = snapshot.stop_cache if snapshot else {}

        # New structures for algorithmic speedups
        self.stop_index = snapshot.stop_index if snapshot else {}
        self.stop_count = len(self.stop_index)
        self.route_patterns = snapshot.route_patterns if snapshot else defaultdict(list)
        self.transfer_cache = snapshot.transfer_cache if snapshot else {}

        # Optional in-memory index
        self.station_time_index = None

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
    def get_departures_from_stop(self, stop_id: int, after_time: datetime, lookahead_minutes: int = 60) -> List[Tuple[datetime, int]]:
        """Get departures from stop after given time, considering real-time delays and cancellations."""
        
        # 1. Base departures from static snapshot
        base_departures = self.departures_by_stop.get(stop_id, [])
        if not base_departures:
            return []

        # 2. Filter via index if available
        candidates = base_departures
        if self.station_time_index is not None:
            try:
                minute_of_day = after_time.hour * 60 + after_time.minute
                entities = self.station_time_index.query(stop_id, minute_of_day, lookahead_minutes)
                candidate_trip_ids = {int(e['entity_id']) for e in entities if e.get('entity_type') == 'trip'}
                if candidate_trip_ids:
                    candidates = [(dt, tid) for dt, tid in base_departures if tid in candidate_trip_ids]
            except Exception:
                pass

        # 3. Apply Real-time Overlay (Phase 2: COW Layer)
        adjusted = []
        for dt, trip_id in candidates:
            if self.overlay.is_cancelled(trip_id):
                continue
            
            delay = self.overlay.get_trip_delay(trip_id)
            effective_time = dt + timedelta(minutes=delay)
            
            if effective_time >= after_time:
                adjusted.append((effective_time, trip_id))

        return sorted(adjusted, key=lambda x: x[0])

    def get_transfers_from_stop(self, stop_id: int, arrival_time: datetime,
                               min_transfer_time: int = 15) -> List[TransferConnection]:
        """Get feasible transfers from stop, honoring real-time state."""
        transfers = self.transfer_graph.get(stop_id, [])
        feasible = []

        for transfer in transfers:
            # Note: In a production overlay, we might also adjust transfer departure times
            # based on the delays of the outgoing trains. We assume the TransferConnection
            # object represents a window and we check feasibility against it.
            if transfer.arrival_time <= arrival_time <= transfer.departure_time:
                duration = (transfer.departure_time - arrival_time).seconds // 60
                if min_transfer_time <= duration <= 8 * 60:
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
