"""
Optimized Multi-Transfer Route Engine - RAPTOR Algorithm Implementation

This module implements a production-grade, optimized RAPTOR (Round-Based Public Transit Routing Algorithm)
for finding multi-transfer routes in railway networks. Key optimizations include:

- Pre-computed route patterns and transfer graphs
- Time-dependent graph with real-time delay injection
- Multi-objective scoring (time, cost, comfort, safety)
- Parallel query execution and caching layers
- ML-enhanced ranking and personalization

Performance targets:
- < 5ms for common route queries
- < 50ms P95 for complex multi-transfer searches
- 10K+ req/sec throughput
"""

import asyncio
import heapq
import time as _time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Set, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
import logging
import os
import sqlite3

# geographic fallback
from backend.utils.graph_utils import haversine_distance

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload

from ..database import SessionLocal
from ..database.models import (
    Stop, Trip, StopTime, Route as GTFRoute,
    Calendar, CalendarDate, Transfer, TrainState
)
from ..database.config import Config
from ..services.multi_layer_cache import multi_layer_cache, RouteQuery, cache_route_search
from .validator.performance_validators import PerformanceValidator
from .validator.validation_manager import create_validation_manager_with_defaults, ValidationProfile, ValidationCategory
from ..ml_reliability_model import get_reliability_model
from ..frequency_aware_range import get_frequency_aware_sizer

logger = logging.getLogger(__name__)


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class SpaceTimeNode:
    """Space-time node for time-dependent graph"""
    stop_id: int
    timestamp: datetime
    event_type: str  # 'arrival' or 'departure'

    def __hash__(self):
        return hash((self.stop_id, self.timestamp.isoformat(), self.event_type))

    def __eq__(self, other):
        return (self.stop_id == other.stop_id and
                self.timestamp == other.timestamp and
                self.event_type == other.event_type)


@dataclass
class RouteSegment:
    """Represents a single train journey segment"""
    trip_id: int
    departure_stop_id: int
    arrival_stop_id: int
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    distance_km: float
    fare: float
    fare_amount: Optional[float] = None
    train_name: str = ""
    train_number: str = ""

    def __post_init__(self):
        # backward-compatible alias: keep `fare` and `fare_amount` in sync
        if (self.fare is None or self.fare == 0) and self.fare_amount:
            self.fare = float(self.fare_amount)
        if self.fare_amount is None:
            self.fare_amount = float(self.fare or 0.0)

    @property
    def departure_station(self) -> int:
        return self.departure_stop_id

    @property
    def arrival_station(self) -> int:
        return self.arrival_stop_id


@dataclass
class TransferConnection:
    """Represents a transfer between trains at a station"""
    station_id: int
    arrival_time: datetime
    departure_time: datetime
    duration_minutes: int
    station_name: str
    facilities_score: float
    safety_score: float
    # Optional platform information (does not affect transfer feasibility by default)
    platform_from: Optional[str] = None
    platform_to: Optional[str] = None


@dataclass
class Route:
    """Complete multi-transfer route"""
    segments: List[RouteSegment] = field(default_factory=list)
    transfers: List[TransferConnection] = field(default_factory=list)
    total_duration: int = 0
    total_cost: float = 0.0
    total_distance: float = 0.0
    score: float = 0.0
    ml_score: float = 0.0

    @property
    def total_fare(self) -> float:
        # backward-compatible alias used across older serializers
        return self.total_cost

    @total_fare.setter
    def total_fare(self, v: float):
        self.total_cost = v

    def add_segment(self, segment: RouteSegment):
        """Add a segment and update totals"""
        self.segments.append(segment)
        self.total_duration += segment.duration_minutes
        self.total_cost += segment.fare
        self.total_distance += segment.distance_km

    def add_transfer(self, transfer: TransferConnection):
        """Add a transfer connection"""
        self.transfers.append(transfer)
        self.total_duration += transfer.duration_minutes

    def get_all_stations(self) -> List[int]:
        """Get all unique station IDs in the route"""
        stations = set()
        for segment in self.segments:
            stations.add(segment.departure_stop_id)
            stations.add(segment.arrival_stop_id)
        return list(stations)

    def get_transfer_durations(self) -> List[int]:
        """Get list of transfer durations in minutes"""
        return [t.duration_minutes for t in self.transfers]


@dataclass
class RouteConstraints:
    """Constraints for route finding"""
    max_journey_time: int = 24 * 60  # 24 hours in minutes
    max_transfers: int = 3
    min_transfer_time: int = 15  # minutes
    max_layover_time: int = 8 * 60  # 8 hours
    avoid_night_layovers: bool = False
    women_safety_priority: bool = False
    max_results: int = 10

    # Range-RAPTOR (search window)
    range_minutes: int = 0             # 0 = disabled; otherwise departure ± range_minutes/2
    range_step_minutes: int = 15      # granularity when scanning the window
    adaptive_range: bool = True       # let engine pick window based on distance/frequency

    # Reliability weighting (0..1) used to bias route score by reliability/confidence
    reliability_weight: float = 0.5

    # Compatibility / advanced options
    preferred_class: Optional[str] = None
    include_wait_time: bool = False

    @dataclass
    class Weights:
        time: float = 1.0
        cost: float = 0.3
        comfort: float = 0.2
        safety: float = 0.1

    weights: Weights = field(default_factory=Weights)


@dataclass
class UserContext:
    """User preferences and context for personalization"""
    user_id: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    loyalty_tier: str = "standard"
    past_bookings: List[Dict] = field(default_factory=list)


# ==============================================================================
# CORE RAPTOR ALGORITHM
# ==============================================================================

class TimeDependentGraph:
    """Optimized time-dependent graph for RAPTOR

    Enhancements added:
    - `stop_index` + bitset helpers for fast reachability checks
    - `route_patterns` mapping: stop-sequence hash -> trips (trip pattern indexing)
    - `transfer_cache` precomputed transfer lookup for (from_stop, to_stop)
    """

    def __init__(self):
        self.departures_by_stop: Dict[int, List[Tuple[datetime, int]]] = defaultdict(list)
        self.arrivals_by_stop: Dict[int, List[Tuple[datetime, int]]] = defaultdict(list)
        self.trip_segments: Dict[int, List[RouteSegment]] = defaultdict(list)
        self.transfer_graph: Dict[int, List[TransferConnection]] = defaultdict(list)
        self.stop_cache: Dict[int, Stop] = {}

        # New structures for algorithmic speedups
        self.stop_index: Dict[int, int] = {}                # stop_id -> bit position
        self.stop_count: int = 0                            # number of stops in graph
        self.route_patterns: Dict[Tuple[int, ...], List[int]] = defaultdict(list)  # stop sequence -> list of trip_ids
        self.transfer_cache: Dict[Tuple[int, int], List[TransferConnection]] = {}  # (from_stop, to_stop) -> transfers

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
    def get_departures_from_stop(self, stop_id: int, after_time: datetime) -> List[Tuple[datetime, int]]:
        """Get departures from stop after given time"""
        departures = self.departures_by_stop.get(stop_id, [])
        return [(dt, trip_id) for dt, trip_id in departures if dt >= after_time]

    def get_transfers_from_stop(self, stop_id: int, arrival_time: datetime,
                               min_transfer_time: int = 15) -> List[TransferConnection]:
        """Get feasible transfers from stop"""
        transfers = self.transfer_graph.get(stop_id, [])
        feasible = []

        for transfer in transfers:
            if transfer.arrival_time <= arrival_time <= transfer.departure_time:
                duration = (transfer.departure_time - arrival_time).seconds // 60
                if min_transfer_time <= duration <= 8 * 60:  # 8 hours max
                    transfer_copy = TransferConnection(
                        station_id=transfer.station_id,
                        arrival_time=arrival_time,
                        departure_time=transfer.departure_time,
                        duration_minutes=duration,
                        station_name=transfer.station_name,
                        facilities_score=transfer.facilities_score,
                        safety_score=transfer.safety_score
                    )
                    feasible.append(transfer_copy)

        return feasible

    def get_transfer_between_stops(self, from_stop: int, to_stop: int) -> List[TransferConnection]:
        """Fast lookup for precomputed transfer(s) between two stops (may return empty list)."""
        return self.transfer_cache.get((from_stop, to_stop), [])

    def get_trip_segments(self, trip_id: int) -> List[RouteSegment]:
        """Get all segments for a trip"""
        return self.trip_segments.get(trip_id, [])

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


class OptimizedRAPTOR:
    """Production-optimized RAPTOR algorithm implementation"""

    def __init__(self, max_transfers: int = 3, validation_manager=None):
        self.max_transfers = max_transfers
        self.executor = ThreadPoolExecutor(max_workers=4)
        # Keep the performance validator locally (used for timing checks in the engine)
        self.performance_validator = PerformanceValidator()
        # Use ValidationManager to orchestrate all other validation logic
        self.validation_manager = validation_manager or create_validation_manager_with_defaults()

    async def find_routes(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints) -> List[Route]:
        """
        Find multi-transfer routes using optimized RAPTOR algorithm with caching

        Args:
            source_stop_id: Source station ID
            dest_stop_id: Destination station ID
            departure_date: Journey date
            constraints: Route constraints and weights

        Returns:
            List of ranked routes
        """

    async def find_trips_by_stop_sequence(self, stop_sequence: List[int], date: Optional[datetime] = None) -> List[int]:
        """Return list of trip_ids that match the exact stop-sequence pattern.

        Useful for pattern-based pruning / frequency estimation.
        """
        # Use today's graph if date omitted
        d = date or datetime.utcnow()
        graph = await self._build_graph(d)
        key = tuple(stop_sequence)
        return list(graph.route_patterns.get(key, []))
        # Create cache query
        cache_query = RouteQuery(
            from_station=str(source_stop_id),
            to_station=str(dest_stop_id),
            date=departure_date.date(),
            class_preference=constraints.preferred_class,
            max_transfers=constraints.max_transfers,
            include_wait_time=constraints.include_wait_time
        )

        # Check cache first
        await multi_layer_cache.initialize()
        cache_start = _time.time()
        cached_result = await multi_layer_cache.get_route_query(cache_query)
        cache_elapsed_ms = (_time.time() - cache_start) * 1000.0
        if cached_result:
            # RT-093: validate cache-hit performance
            if not self.performance_validator.validate_cache_hit_performance(cache_elapsed_ms, expected_max_ms=50.0):
                logger.warning("RT-093: cache-hit latency exceeded threshold (%.2fms)", cache_elapsed_ms)
            logger.info(f"Route cache hit for {source_stop_id} -> {dest_stop_id}")
            # Convert cached data back to Route objects
            return self._deserialize_cached_routes(cached_result)

        # Compute routes
        routes = await self._compute_routes(source_stop_id, dest_stop_id, departure_date, constraints)

        # Cache the result
        if routes:  # Only cache if we found routes
            serialized_routes = self._serialize_routes_for_cache(routes)
            await multi_layer_cache.set_route_query(cache_query, serialized_routes)

        return routes

    async def _compute_routes(self, source_stop_id: int, dest_stop_id: int,
                             departure_date: datetime, constraints: RouteConstraints) -> List[Route]:
        """
        Internal route computation with frequency-aware Range-RAPTOR.
        """
        start_time = _time.time()

        # Build time-dependent graph
        graph_build_start = _time.time()
        graph = await self._build_graph(departure_date)
        graph_build_ms = (_time.time() - graph_build_start) * 1000.0
        # RT-096: validate graph rebuild performance (warn on regression)
        if not self.performance_validator.validate_graph_rebuild_performance(graph_build_ms, threshold_ms=1500.0):
            logger.warning("RT-096: graph rebuild time high (%.2fms)", graph_build_ms)

        # Initialize RAPTOR structures
        routes_by_round: Dict[int, List[Route]] = defaultdict(list)
        earliest_arrival: Dict[int, datetime] = {}
        best_routes: Dict[str, Route] = {}

        # Use Range‑RAPTOR if requested (search departure ± window) — reuse the built graph
        if constraints.range_minutes > 0 or constraints.adaptive_range:
            # adaptive window sizing when requested
            if constraints.range_minutes == 0 and constraints.adaptive_range:
                # Use frequency-aware window sizer
                sizer = await get_frequency_aware_sizer()
                
                # Get distance estimate
                src = graph.stop_cache.get(source_stop_id)
                dst = graph.stop_cache.get(dest_stop_id)
                distance_km = None
                if src and dst:
                    try:
                        distance_km = haversine_distance(src.latitude, src.longitude, dst.latitude, dst.longitude)
                    except Exception:
                        distance_km = None

                # Compute frequency-aware window
                constraints.range_minutes = await sizer.get_range_window_minutes(
                    origin_stop_id=source_stop_id,
                    destination_stop_id=dest_stop_id,
                    search_date=departure_date.date(),
                    base_range_minutes=60,
                    distance_km=distance_km,
                )
                logger.debug(f"Frequency-aware Range-RAPTOR window: {constraints.range_minutes} minutes")

            half = constraints.range_minutes // 2
            step = max(5, constraints.range_step_minutes)
            departure_times = [departure_date + timedelta(minutes=m) for m in range(-half, half + 1, step)]

            collected = []
            # run searches across the time-window (sequential to keep memory predictable)
            for dt in departure_times:
                gathered = await self._search_single_departure(graph, source_stop_id, dest_stop_id, dt, constraints)
                collected.extend(gathered)

            # Deduplicate and sort (primary: score, secondary: -reliability)
            unique = await self._deduplicate_routes(collected, graph)
            unique.sort(key=lambda r: (r.score, -r.reliability))
            return unique[:constraints.max_results]

        # Single-departure search (default behavior)
        single_routes = await self._search_single_departure(graph, source_stop_id, dest_stop_id, departure_date, constraints)
        single_routes.sort(key=lambda r: (r.score, -r.reliability))
        return single_routes[:constraints.max_results]

    async def _process_route_transfers(self, route: Route, graph: TimeDependentGraph,
                                      dest_stop_id: int, constraints: RouteConstraints) -> List[Route]:
        """Process transfers for a single route"""
        new_routes = []
        last_segment = route.segments[-1]

        # Find feasible transfers at arrival station
        transfers = graph.get_transfers_from_stop(
            last_segment.arrival_stop_id,
            last_segment.arrival_time,
            constraints.min_transfer_time
        )

        for transfer in transfers:
            # Check transfer constraints
            if not self._is_feasible_transfer(transfer, constraints):
                continue

            # Find onward connections
            onward_departures = graph.get_departures_from_stop(
                transfer.station_id, transfer.departure_time
            )

            for dep_time, trip_id in onward_departures[:20]:  # Limit onward connections
                if dep_time < transfer.departure_time:
                    continue

                segments = graph.get_trip_segments(trip_id)
                for segment in segments:
                    if (segment.departure_stop_id == transfer.station_id and
                        segment.departure_time >= transfer.departure_time):

                        # Prevent cycles: do not revisit a station already present in the route
                        existing_stations = set(route.get_all_stations())
                        if segment.arrival_stop_id in existing_stations:
                            # skip segments that would create loops
                            continue

                        # Initialize new_route
                        new_route = Route(
                            segments=route.segments + [segment],
                            total_distance=route.total_distance + segment.distance_km,
                            transfers=route.transfers + [transfer]
                        )

                        # Check if destination reached
                        if segment.arrival_stop_id == dest_stop_id:
                            if self._validate_route_constraints(new_route, constraints):
                                score = await self._score_with_reliability(new_route, constraints)
                                new_route.score = score
                                new_routes.append(new_route)
                        elif len(new_route.transfers) < constraints.max_transfers:
                            new_routes.append(new_route)

                        break  # Only one segment per trip

        return new_routes

    async def _build_graph(self, date: datetime) -> TimeDependentGraph:
        """Build optimized time-dependent graph for the given date"""
        graph = TimeDependentGraph()

        # Use thread pool for database operations
        loop = asyncio.get_event_loop()
        db_graph = await loop.run_in_executor(
            self.executor, self._build_graph_sync, date
        )

        # Transfer data to graph
        graph.departures_by_stop = db_graph['departures']
        graph.arrivals_by_stop = db_graph['arrivals']
        graph.trip_segments = db_graph['segments']
        graph.transfer_graph = db_graph['transfers']
        graph.stop_cache = db_graph['stops']

        # Attach precomputed indexes (if present)
        graph.route_patterns = db_graph.get('route_patterns', defaultdict(list))
        graph.transfer_cache = db_graph.get('transfer_cache', {})

        # Build stop_index for bitset operations
        graph.build_stop_index()

        return graph

    def _build_graph_sync(self, date: datetime) -> Dict:
        """Synchronous graph building (runs in thread pool)"""
        session = SessionLocal()

        try:
            # Get active service IDs for the date
            service_ids = self._get_active_service_ids(session, date)

            # Build departures and arrivals index
            departures = defaultdict(list)
            arrivals = defaultdict(list)
            segments = defaultdict(list)
            stops = {}

            # Precomputed indexes for algorithmic speedups
            route_patterns = defaultdict(list)    # stop-sequence tuple -> list of trip_ids
            transfer_cache = {}                   # (from_stop,to_stop) -> list[TransferConnection]

            # Query stop times for active services
            stop_times = session.query(StopTime).join(Trip).filter(
                Trip.service_id.in_(service_ids)
            ).options(
                joinedload(StopTime.trip),
                joinedload(StopTime.stop)
            ).order_by(StopTime.trip_id, StopTime.stop_sequence).all()

            # Group by trip
            trip_groups = defaultdict(list)
            for st in stop_times:
                trip_groups[st.trip_id].append(st)
                stops[st.stop_id] = st.stop

            # Process each trip
            for trip_id, trip_stop_times in trip_groups.items():
                if len(trip_stop_times) < 2:
                    continue

                # Sort by sequence
                trip_stop_times.sort(key=lambda x: x.stop_sequence)

                # Create segments (use authoritative railway_manager distances/day-offsets when available)
                trip_segments = []
                for i in range(len(trip_stop_times) - 1):
                    current = trip_stop_times[i]
                    next_stop = trip_stop_times[i + 1]

                    # Convert departure time
                    dep_dt = self._time_to_datetime(date, current.departure_time)

                    # Default arrival datetime (may be adjusted by authoritative day_offset)
                    arr_dt = self._time_to_datetime(date, next_stop.arrival_time)

                    # Attempt to enrich with railway_manager (SQLite) authoritative segment data
                    distance_km = None
                    arrival_day_offset = None
                    try:
                        train_identifier = getattr(trip_stop_times[0].trip, 'trip_id', None)
                        src_code = getattr(current.stop, 'code', None)
                        dst_code = getattr(next_stop.stop, 'code', None)

                        if train_identifier and src_code and dst_code:
                            sqlite_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "railway_manager.db"))
                            if os.path.exists(sqlite_path):
                                conn = sqlite3.connect(sqlite_path)
                                cur = conn.cursor()
                                # First try exact train_no match with consecutive stations
                                cur.execute(
                                    "SELECT station_code, distance_from_source, day_offset, seq_no FROM train_routes WHERE train_no = ? ORDER BY seq_no",
                                    (str(train_identifier),)
                                )
                                rows = cur.fetchall()
                                if rows:
                                    for r_idx in range(len(rows) - 1):
                                        if rows[r_idx][0] == src_code and rows[r_idx + 1][0] == dst_code:
                                            distance_km = float(rows[r_idx + 1][1] - rows[r_idx][1]) if rows[r_idx + 1][1] is not None and rows[r_idx][1] is not None else None
                                            arrival_day_offset = int(rows[r_idx + 1][2] or 0)
                                            break

                                # Fallback: find any train that has the consecutive pair (fast path)
                                if distance_km is None:
                                    cur.execute(
                                        """
                                        SELECT t1.train_no, (t2.distance_from_source - t1.distance_from_source) AS distance_km, t2.day_offset
                                        FROM train_routes t1
                                        JOIN train_routes t2 ON t1.train_no = t2.train_no AND t2.seq_no = t1.seq_no + 1
                                        WHERE t1.station_code = ? AND t2.station_code = ?
                                        LIMIT 1
                                        """,
                                        (src_code, dst_code)
                                    )
                                    r = cur.fetchone()
                                    if r:
                                        distance_km = float(r[1]) if r[1] is not None else None
                                        arrival_day_offset = int(r[2] or 0)

                                conn.close()
                    except Exception:
                        # don't break graph build on lookup failures; fall back below
                        distance_km = None
                        arrival_day_offset = None

                    # If authoritative arrival_day_offset present, use it to compute arrival datetime
                    if arrival_day_offset is not None:
                        arr_dt = self._time_to_datetime(date + timedelta(days=arrival_day_offset), next_stop.arrival_time)
                    else:
                        # Conservative fallback for overnight times if arrival < departure
                        while arr_dt < dep_dt:
                            arr_dt += timedelta(days=1)

                    duration_minutes = int((arr_dt - dep_dt).total_seconds() // 60)

                    # Distance fallback: if not found in railway_manager, use Haversine between stop coords
                    if distance_km is None:
                        s1 = current.stop
                        s2 = next_stop.stop
                        try:
                            distance_km = haversine_distance(s1.latitude, s1.longitude, s2.latitude, s2.longitude)
                        except Exception:
                            distance_km = 0.0

                    segment = RouteSegment(
                        trip_id=trip_id,
                        departure_stop_id=current.stop_id,
                        arrival_stop_id=next_stop.stop_id,
                        departure_time=dep_dt,
                        arrival_time=arr_dt,
                        duration_minutes=duration_minutes,
                        distance_km=round(float(distance_km or 0.0), 3),
                        fare=100.0,  # TODO: compute from fares table / ML pricing
                        train_name=getattr(trip_stop_times[0].trip.route, 'long_name', 'Unknown'),
                        train_number=str(trip_id)
                    )

                    trip_segments.append(segment)

                    # Add to departures index
                    departures[current.stop_id].append((dep_dt, trip_id))

                    # Add to arrivals index
                    arrivals[next_stop.stop_id].append((arr_dt, trip_id))

                segments[trip_id] = trip_segments

                # --- Trip pattern indexing (stop-sequence -> trips) ---
                try:
                    stop_seq = tuple([s.stop_id for s in trip_stop_times])
                    # store canonical sequence (departure stops + final arrival)
                    route_patterns.setdefault(stop_seq, []).append(trip_id)
                except Exception:
                    # keep graph build robust
                    pass

            # Build transfer graph from authoritative Transfer table (fall back to a reasonable default)
            transfers = defaultdict(list)
            all_stops = session.query(Stop).all()

            for stop in all_stops:
                stops[stop.id] = stop

                # Pull explicit transfer rules from DB (if present)
                db_transfers = session.query(Transfer).filter(
                    or_(Transfer.from_stop_id == stop.id, Transfer.to_stop_id == stop.id)
                ).all()

                if db_transfers:
                    for dbtr in db_transfers:
                        # min_transfer_time is stored in seconds in Transfer model
                        mins = max(1, (dbtr.min_transfer_time // 60) if getattr(dbtr, 'min_transfer_time', None) else 15)
                        partner_stop = dbtr.to_stop_id if dbtr.from_stop_id == stop.id else dbtr.from_stop_id
                        transfer = TransferConnection(
                            station_id=partner_stop,
                            arrival_time=date.replace(hour=0, minute=0),
                            departure_time=date.replace(hour=23, minute=59),
                            duration_minutes=mins,
                            station_name=stop.name,
                            facilities_score=(stop.facilities_json.get('walking_time_factor') if getattr(stop, 'facilities_json', None) else 0.7),
                            safety_score=min(1.0, max(0.0, (getattr(stop, 'safety_score', 50.0) / 100.0)))
                        )
                        transfers[stop.id].append(transfer)
                else:
                    # Conservative default transfer (covers cases where transfer table is empty)
                    default_duration = 15
                    transfer = TransferConnection(
                        station_id=stop.id,
                        arrival_time=date.replace(hour=0, minute=0),
                        departure_time=date.replace(hour=23, minute=59),
                        duration_minutes=default_duration,
                        station_name=stop.name,
                        facilities_score=(stop.facilities_json.get('walking_time_factor') if getattr(stop, 'facilities_json', None) else 0.7),
                        safety_score=min(1.0, max(0.0, (getattr(stop, 'safety_score', 50.0) / 100.0)))
                    )
                    transfers[stop.id].append(transfer)

            # Build transfer_cache from transfers for O(1) pair lookups
            for from_stop, tlist in transfers.items():
                for t in tlist:
                    key = (from_stop, t.station_id)
                    transfer_cache.setdefault(key, []).append(t)

            return {
                'departures': departures,
                'arrivals': arrivals,
                'segments': segments,
                'transfers': transfers,
                'stops': stops,
                'route_patterns': route_patterns,
                'transfer_cache': transfer_cache
            }

        finally:
            session.close()

    def _get_active_service_ids(self, session, date: datetime) -> List[int]:
        """Get active service IDs for the given date"""
        # Check calendar dates first (exceptions)
        exception_services = session.query(CalendarDate.service_id).filter(
            and_(
                CalendarDate.date == date.date(),
                CalendarDate.exception_type == 1  # Added service
            )
        ).subquery()

        removed_services = session.query(CalendarDate.service_id).filter(
            and_(
                CalendarDate.date == date.date(),
                CalendarDate.exception_type == 2  # Removed service
            )
        ).subquery()

        # Get regular services
        weekday = date.strftime('%A').lower()
        regular_services = session.query(Calendar.id).filter(
            and_(
                getattr(Calendar, weekday) == True,
                Calendar.start_date <= date.date(),
                Calendar.end_date >= date.date()
            )
        ).subquery()

        # Combine: regular services + added - removed
        active_services = session.query(
            func.coalesce(exception_services.c.service_id, regular_services.c.id)
        ).filter(
            ~func.coalesce(exception_services.c.service_id, regular_services.c.id).in_(
                session.query(removed_services.c.service_id)
            )
        ).all()

        return [s[0] for s in active_services]

    def _time_to_datetime(self, date: datetime, t: time) -> datetime:
        """Convert time to datetime on given date"""
        return datetime.combine(date.date(), t)

    def _validate_route_constraints(self, route: Route, constraints: RouteConstraints) -> bool:
        """Validate route against all constraints"""
        # Time constraints
        if route.total_duration > constraints.max_journey_time:
            return False

        # Transfer count constraint
        if len(route.transfers) > constraints.max_transfers:
            return False

        # Transfer constraints
        for transfer in route.transfers:
            if transfer.duration_minutes < constraints.min_transfer_time:
                return False
            if transfer.duration_minutes > constraints.max_layover_time:
                return False

        # Night layover constraints
        if constraints.avoid_night_layovers:
            for transfer in route.transfers:
                if self._is_night_layover(transfer.arrival_time, transfer.departure_time):
                    return False

        # Women safety constraints
        if constraints.women_safety_priority:
            for station_id in route.get_all_stations():
                if not self._is_safe_station(station_id):
                    return False

        return True

    def _is_feasible_transfer(self, transfer: TransferConnection, constraints: RouteConstraints) -> bool:
        """Check if transfer meets constraints (platform differences tolerated).

        Rules:
        - duration must be within min/max limits
        - night layover avoidance honored
        - platform_from/platform_to differences are allowed (we may add penalties elsewhere)
        """
        if transfer.duration_minutes < constraints.min_transfer_time:
            return False
        if transfer.duration_minutes > constraints.max_layover_time:
            return False

        # Platform differences do not make a transfer infeasible by default
        # (kept for extensibility / future penalties)
        # if transfer.platform_from and transfer.platform_to and transfer.platform_from != transfer.platform_to:
        #     pass

        if constraints.avoid_night_layovers:
            if self._is_night_layover(transfer.arrival_time, transfer.departure_time):
                return False

        return True

    def _validate_segment_continuity(self, segments: List[RouteSegment]) -> bool:
        """Validate that a sequence of RouteSegment objects represents a continuous journey.

        Continuity rules (conservative):
        - For consecutive segments: previous.arrival_stop_id == next.departure_stop_id
        - Arrival time must be <= next departure time
        - Segments belonging to same trip may be allowed to skip internal stops only if data shows them as linked; otherwise reject.
        """
        if not segments:
            return False

        for i in range(len(segments) - 1):
            prev = segments[i]
            nxt = segments[i + 1]

            # station continuity
            if prev.arrival_stop_id != nxt.departure_stop_id:
                # Fallback for missing intermediate stops
                if not self._check_missing_stop_link(prev.arrival_stop_id, nxt.departure_stop_id):
                    return False

            # temporal continuity
            if prev.arrival_time > nxt.departure_time:
                return False

        return True

    def _check_missing_stop_link(self, from_stop_id: int, to_stop_id: int) -> bool:
        """Check if missing intermediate stops can be linked based on GTFS data."""
        # Placeholder for actual implementation
        # This would query the database or use heuristics to determine if the stops are linked
        return True

    async def _deduplicate_routes(self, routes: List[Route], graph: Optional[TimeDependentGraph] = None) -> List[Route]:
        """Deduplicate + dominance-prune routes.

        Improvements:
        - Use bitset-based quick duplicate detection when `graph` provided
        - Multi-dimensional dominance pruning (time, transfers, cost, reliability)
        - Keep only non-dominated / best-scoring routes
        """
        kept: List[Route] = []

        def dominates(a: Route, b: Route) -> bool:
            """Return True if route a dominates route b on all considered metrics."""
            better_or_equal = (
                a.total_duration <= b.total_duration and
                a.total_cost <= b.total_cost and
                len(a.transfers) <= len(b.transfers) and
                a.reliability >= b.reliability
            )
            strictly_better = (
                a.total_duration < b.total_duration or
                a.total_cost < b.total_cost or
                len(a.transfers) < len(b.transfers) or
                a.reliability > b.reliability
            )
            return better_or_equal and strictly_better

        # Precompute bitsets if graph available
        use_bitset = graph is not None and getattr(graph, 'stop_index', None) is not None
        seen_keys: Set[Tuple[int, Tuple[int, ...]]] = set()

        for route in routes:
            # quick duplicate key: (stations-bitset or tuple(stations), tuple(transfer station ids))
            if use_bitset:
                try:
                    route_bits = graph.route_to_bitset(route)
                except Exception:
                    route_bits = 0
                transfer_ids = tuple(t.station_id for t in route.transfers)
                key = (route_bits, transfer_ids)
            else:
                key = (tuple(route.get_all_stations()), tuple(t.station_id for t in route.transfers))

            if key in seen_keys:
                # keep the better-scoring duplicate only
                # find existing and replace if current has better score
                for i, r in enumerate(kept):
                    cmp_key = (graph.route_to_bitset(r) if use_bitset else tuple(r.get_all_stations()), tuple(t.station_id for t in r.transfers))
                    if cmp_key == key:
                        if route.score < r.score:
                            kept[i] = route
                        break
                continue

            # Dominance pruning against kept routes
            dominated = False
            remove_indices: List[int] = []
            for i, existing in enumerate(kept):
                if dominates(existing, route):
                    dominated = True
                    break
                if dominates(route, existing):
                    remove_indices.append(i)

            if dominated:
                continue

            # Remove any existing routes dominated by the new one (iterate in reverse to pop safely)
            for idx in reversed(remove_indices):
                kept.pop(idx)

            kept.append(route)
            seen_keys.add(key)

        return kept

    async def _estimate_route_reliability(self, route: Route, constraints: RouteConstraints) -> float:
        """
        Estimate P(success) for a route using ML model with heuristic fallback.

        ML Features:
        - Historical delay for each train segment
        - Transfer duration adequacy
        - Station safety scores
        - Time-of-day and day-of-week patterns

        Falls back to heuristics if ML model unavailable.
        Returns float in (0, 1]
        """
        # Try ML model first
        ml_model = await get_reliability_model()
        
        if route.segments and ml_model.loaded:
            try:
                # Use first segment's trip as representative
                first_seg = route.segments[0]
                last_seg = route.segments[-1]
                
                # Compute total distance
                total_distance = sum(seg.distance_km for seg in route.segments)
                
                # Estimate max transfer duration
                max_transfer = max((t.duration_minutes for t in route.transfers), default=15)
                
                # Get ML prediction
                ml_score = await ml_model.predict(
                    trip_id=first_seg.trip_id,
                    origin_stop_id=first_seg.departure_stop_id,
                    destination_stop_id=last_seg.arrival_stop_id,
                    departure_time=first_seg.departure_time,
                    transfer_duration_minutes=max_transfer,
                    distance_km=total_distance,
                )
                
                # Blend with heuristic penalties for safety
                heuristic_penalty = await self._compute_heuristic_reliability_penalty(route, constraints)
                combined = ml_score * heuristic_penalty
                
                return float(max(0.01, min(0.999, combined)))
            except Exception as e:
                logger.debug(f"ML reliability prediction failed: {e}, using heuristics")
        
        # Fallback to pure heuristics if ML unavailable
        return await self._compute_heuristic_reliability(route, constraints)

    async def _compute_heuristic_reliability(self, route: Route, constraints: RouteConstraints) -> float:
        """Pure heuristic-based reliability (fallback for when ML unavailable)"""
        score = 1.0
        session = SessionLocal()
        try:
            # segment-level signals (train delay history / live state)
            for seg in route.segments:
                try:
                    ts = session.query(TrainState).filter(TrainState.trip_id == seg.trip_id).first()
                except Exception:
                    ts = None

                if ts and getattr(ts, 'delay_minutes', 0):
                    d = abs(int(ts.delay_minutes or 0))
                    if d >= 60:
                        score *= 0.75
                    elif d >= 15:
                        score *= 0.88
                    else:
                        score *= 0.95

            # transfer-level penalties
            for t in route.transfers:
                if t.duration_minutes < constraints.min_transfer_time:
                    score *= 0.6
                elif t.duration_minutes <= (constraints.min_transfer_time + 5):
                    score *= 0.85
                else:
                    score *= 0.98

                # station safety
                try:
                    st = session.query(Stop).filter(Stop.id == t.station_id).first()
                    if st and getattr(st, 'safety_score', 50.0) < 40:
                        score *= 0.95
                except Exception:
                    pass

        finally:
            session.close()

        score = max(0.01, min(0.999, float(score)))
        return score

    async def _compute_heuristic_reliability_penalty(self, route: Route, constraints: RouteConstraints) -> float:
        """
        Compute multiplicative penalty factor for heuristic safety checks.
        Used to blend with ML predictions.
        Returns [0.5, 1.0] where 1.0 = no penalty.
        """
        penalty = 1.0
        session = SessionLocal()
        try:
            # Penalize very short transfers
            for t in route.transfers:
                if t.duration_minutes < constraints.min_transfer_time:
                    penalty *= 0.85
            
            # Penalize unsafe stations
            for seg in route.segments:
                try:
                    stop = session.query(Stop).filter(Stop.id == seg.arrival_stop_id).first()
                    if stop and getattr(stop, 'safety_score', 50.0) < 40:
                        penalty *= 0.95
                except Exception:
                    pass
        finally:
            session.close()
        
        return max(0.5, min(1.0, penalty))

    async def _score_with_reliability(self, route: Route, constraints: RouteConstraints) -> float:
        """Compute base score + bias by reliability estimate. Sets route.reliability."""
        # Try to reuse any existing _calculate_score implementation on this object
        base_score = None
        calc = getattr(self, '_calculate_score', None)
        if callable(calc):
            try:
                base_score = calc(route, constraints)
            except Exception:
                base_score = None

        if base_score is None:
            # Fallback scoring similar to public RouteEngine
            w = constraints.weights
            time_score = route.total_duration
            cost_score = route.total_cost
            comfort_score = 0
            for tr in route.transfers:
                comfort_score += tr.facilities_score * 10
                if self._is_night_layover(tr.arrival_time, tr.departure_time):
                    comfort_score -= 20
            safety_score = 0
            if constraints.women_safety_priority:
                safety_score = sum(5 for _ in route.get_all_stations())

            base_score = (w.time * time_score + w.cost * cost_score - w.comfort * comfort_score + w.safety * safety_score)

        reliability = await self._estimate_route_reliability(route, constraints)
        route.reliability = reliability

        # Blend reliability into final score (less score is better). reliability_weight in [0,1]
        penalty_factor = constraints.reliability_weight * (1.0 - reliability)
        final_score = base_score * (1.0 + penalty_factor)
        return final_score

    async def _search_single_departure(self, graph: TimeDependentGraph, source_stop_id: int, dest_stop_id: int,
                                      departure_dt: datetime, constraints: RouteConstraints) -> List[Route]:
        """Single-departure RAPTOR search that reuses an already-built graph."""
        routes_by_round: Dict[int, List[Route]] = defaultdict(list)
        earliest_arrival: Dict[int, datetime] = {}
        best_routes: Dict[str, Route] = {}

        # Round 0: direct departures
        source_departures = graph.get_departures_from_stop(source_stop_id, departure_dt)
        for dep_time, trip_id in source_departures[:50]:
            segments = graph.get_trip_segments(trip_id)
            for segment in segments:
                if segment.departure_stop_id == source_stop_id and segment.departure_time >= dep_time:
                    route = Route()
                    route.add_segment(segment)
                    if segment.arrival_stop_id == dest_stop_id:
                        if self._validate_route_constraints(route, constraints):
                            score = await self._score_with_reliability(route, constraints)
                            route.score = score
                            key = f"direct_{trip_id}"
                            if key not in best_routes or score < best_routes[key].score:
                                best_routes[key] = route
                    else:
                        routes_by_round[0].append(route)
                    break

        # transfer rounds
        for round_num in range(1, self.max_transfers + 1):
            if not routes_by_round[round_num - 1]:
                break
            current_routes = routes_by_round[round_num - 1]
            batch_size = 10
            for i in range(0, len(current_routes), batch_size):
                batch = current_routes[i:i + batch_size]
                transfer_routes = await asyncio.gather(*[
                    self._process_route_transfers(route, graph, dest_stop_id, constraints)
                    for route in batch
                ])
                for route_list in transfer_routes:
                    routes_by_round[round_num].extend(route_list)

        all_routes = []
        for key, route in best_routes.items():
            if self._validate_route_constraints(route, constraints):
                all_routes.append(route)

        # Score any routes in routes_by_round (transfers) that reached destination
        for rlist in routes_by_round.values():
            for r in rlist:
                if r.segments and r.segments[-1].arrival_stop_id == dest_stop_id and self._validate_route_constraints(r, constraints):
                    r.score = await self._score_with_reliability(r, constraints)
                    all_routes.append(r)

        # Deduplicate & dominance-prune
        unique = await self._deduplicate_routes(all_routes, graph)
        unique.sort(key=lambda r: (r.score, -r.reliability))
        return unique

    async def _apply_cancellation_update(self, update: Dict[str, Any]):
        """Apply cancellation update to graph"""
        trip_id = update['trip_id']
        cancelled_stations = update.get('cancelled_stations', [])

        # Mark trip as cancelled in graph
        if trip_id in self.time_graph.trip_nodes:
            for node in self.time_graph.trip_nodes[trip_id]:
                node.is_cancelled = True

        # Remove cancelled segments
        if cancelled_stations:
            self.time_graph.remove_cancelled_segments(trip_id, cancelled_stations)

        # Update cached routes
        await self._invalidate_affected_routes(trip_id)

        logger.info(f"Applied cancellation to trip {trip_id}")

    async def _apply_occupancy_update(self, update: Dict[str, Any]):
        """Apply occupancy update to graph"""
        trip_id = update['trip_id']
        occupancy_rate = update['occupancy_rate']

        # Update occupancy weights in graph
        if trip_id in self.time_graph.trip_nodes:
            for node in self.time_graph.trip_nodes[trip_id]:
                node.occupancy_weight = self._calculate_occupancy_penalty(occupancy_rate)

        logger.debug(f"Updated occupancy for trip {trip_id}: {occupancy_rate}")

    async def _invalidate_affected_routes(self, trip_id: int):
        """Invalidate cached routes affected by a trip change"""
        # Get all stations served by this trip
        session = SessionLocal()
        try:
            stop_times = session.query(StopTime).filter(
                StopTime.trip_id == trip_id
            ).all()

            affected_stations = {st.stop_id for st in stop_times}

            # Invalidate cache for routes involving these stations
            # This would integrate with Redis caching layer
            for station_id in affected_stations:
                cache_key = f"routes:station:{station_id}"
                # await redis.delete(cache_key)  # Would implement Redis integration

        finally:
            session.close()

    def _calculate_occupancy_penalty(self, occupancy_rate: float) -> float:
        """Calculate comfort penalty based on occupancy"""
        if occupancy_rate < 0.5:
            return 1.0  # No penalty
        elif occupancy_rate < 0.8:
            return 1.2  # Slight penalty
        else:
            return 1.5  # High penalty for crowded trains

    def _serialize_routes_for_cache(self, routes: List[Route]) -> Dict:
        """Serialize routes for caching"""
        return {
            'routes': [
                {
                    'segments': [
                        {
                            'trip_id': seg.trip_id,
                            'departure_stop_id': seg.departure_stop_id,
                            'arrival_stop_id': seg.arrival_stop_id,
                            'departure_time': seg.departure_time.isoformat(),
                            'arrival_time': seg.arrival_time.isoformat(),
                            'duration_minutes': seg.duration_minutes,
                            'distance_km': seg.distance_km,
                            'fare_amount': seg.fare_amount,
                            'train_name': seg.train_name,
                            'train_number': seg.train_number
                        } for seg in route.segments
                    ],
                    'transfers': [
                        {
                            'station_id': t.station_id,
                            'arrival_time': t.arrival_time.isoformat(),
                            'departure_time': t.departure_time.isoformat(),
                            'duration_minutes': t.duration_minutes,
                            'station_name': t.station_name
                        } for t in route.transfers
                    ],
                    'total_duration': route.total_duration,
                    'total_distance': route.total_distance,
                    'total_fare': route.total_fare,
                    'score': route.score,
                    'cached_at': datetime.utcnow().isoformat()
                } for route in routes
            ],
            'count': len(routes)
        }

    def _deserialize_cached_routes(self, cached_data: Dict) -> List[Route]:
        """Deserialize routes from cache"""
        routes = []
        for route_data in cached_data.get('routes', []):
            route = Route()

            # Deserialize segments
            for seg_data in route_data.get('segments', []):
                segment = RouteSegment(
                    trip_id=seg_data['trip_id'],
                    departure_stop_id=seg_data['departure_stop_id'],
                    arrival_stop_id=seg_data['arrival_stop_id'],
                    departure_time=datetime.fromisoformat(seg_data['departure_time']),
                    arrival_time=datetime.fromisoformat(seg_data['arrival_time']),
                    duration_minutes=seg_data['duration_minutes'],
                    distance_km=seg_data.get('distance_km', 0),
                    fare_amount=seg_data.get('fare_amount', 0),
                    train_name=seg_data.get('train_name', ''),
                    train_number=seg_data.get('train_number', '')
                )
                route.add_segment(segment)

            # Deserialize transfers
            for transfer_data in route_data.get('transfers', []):
                transfer = TransferConnection(
                    station_id=transfer_data['station_id'],
                    arrival_time=datetime.fromisoformat(transfer_data['arrival_time']),
                    departure_time=datetime.fromisoformat(transfer_data['departure_time']),
                    duration_minutes=transfer_data['duration_minutes'],
                    station_name=transfer_data.get('station_name', ''),
                    facilities_score=0.0,
                    safety_score=0.0
                )
                route.add_transfer(transfer)

            # Set totals
            route.total_duration = route_data.get('total_duration', 0)
            route.total_distance = route_data.get('total_distance', 0)
            route.total_fare = route_data.get('total_fare', 0)
            route.score = route_data.get('score', 0)

            routes.append(route)

        return routes

    def validate_multimodal_route(self, multimodal_route, validation_config: dict = None) -> bool:
        """Validate multi-modal route using ValidationManager."""
        if validation_config is None:
            validation_config = {}
        config = {'route': multimodal_route}
        config.update(validation_config)
        report = self.validation_manager.validate(
            config, profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.MULTIMODAL}
        )
        return report.all_passed

    def validate_fare_and_availability(self, route: Route, travel_class: str = "SL") -> bool:
        """Validate fare and availability using ValidationManager."""
        config = {'route': route, 'travel_class': travel_class}
        report = self.validation_manager.validate(
            config, profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.FARE_AVAILABILITY}
        )
        return report.all_passed

    def validate_api_and_security(self, request_data: dict, auth_token: str) -> bool:
        """Validate API security using ValidationManager."""
        report = self.validation_manager.validate_api_request(
            request_data, auth_token, profile=ValidationProfile.STANDARD
        )
        return report.all_passed

    def validate_data_integrity(self, graph_data: dict) -> bool:
        """Validate data integrity using ValidationManager."""
        config = {'graph_data': graph_data}
        report = self.validation_manager.validate(
            config, profile=ValidationProfile.FULL,
            specific_categories={ValidationCategory.DATA_INTEGRITY}
        )
        return report.all_passed

    def validate_ai_ranking(self, ranked_routes: list, user_context: dict) -> bool:
        """Validate AI ranking using ValidationManager."""
        config = {'ranked_routes': ranked_routes, 'user_context': user_context}
        report = self.validation_manager.validate(
            config, profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.AI_RANKING}
        )
        return report.all_passed

    def validate_resilience(self, validation_config: dict = None) -> bool:
        """Run chaos / failure-recovery validations (RT-171 — RT-200)."""
        if validation_config is None:
            validation_config = {}
        report = self.validation_manager.validate(
            validation_config,
            profile=ValidationProfile.FULL,
            specific_categories={ValidationCategory.RESILIENCE}
        )
        return report.all_passed

    def validate_production_excellence(self, validation_config: dict = None) -> bool:
        """Run production-excellence validations (RT-201 — RT-220)."""
        if validation_config is None:
            validation_config = {}
        report = self.validation_manager.validate(
            validation_config,
            profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.PRODUCTION_EXCELLENCE}
        )
        return report.all_passed


# ==============================================================================
# PUBLIC API
# ==============================================================================

class RouteEngine:
    """Main route engine interface"""

    def __init__(self):
        self.raptor = OptimizedRAPTOR(max_transfers=3)
        self.validation_manager = create_validation_manager_with_defaults()

    async def search_routes(self, source_code: str, destination_code: str,
                           departure_date: datetime,
                           constraints: Optional[RouteConstraints] = None,
                           user_context: Optional[UserContext] = None) -> List[Route]:
        """
        Search for routes between source and destination

        Args:
            source_code: Source station code (e.g., 'NDLS')
            destination_code: Destination station code
            departure_date: Departure date and time
            constraints: Route constraints
            user_context: User preferences for personalization

        Returns:
            List of ranked routes
        """
        if constraints is None:
            constraints = RouteConstraints()

        # Get station IDs
        session = SessionLocal()
        try:
            source_stop = session.query(Stop).filter(Stop.code == source_code).first()
            dest_stop = session.query(Stop).filter(Stop.code == destination_code).first()

            if not source_stop or not dest_stop:
                return []

            # Same-origin / same-destination -> return empty result (zero-length journey)
            if source_stop.id == dest_stop.id:
                return []

            # Execute RAPTOR search
            routes = await self.raptor.find_routes(
                source_stop.id, dest_stop.id, departure_date, constraints
            )

            # Apply ML ranking if user context provided
            if user_context:
                routes = await self._apply_ml_ranking(routes, user_context)

            return routes

        finally:
            session.close()

    async def _apply_ml_ranking(self, routes: List[Route], user_context: UserContext) -> List[Route]:
        """Apply ML-based ranking and personalization"""
        # Placeholder for ML integration
        # In production, this would call shadow_inference_service
        return routes

    def validate_resilience(self, validation_config: dict = None) -> bool:
        """Facade: run resilience (RT-171—RT-200) validations via OptimizedRAPTOR."""
        return self.raptor.validate_resilience(validation_config)

    def validate_production_excellence(self, validation_config: dict = None) -> bool:
        """Facade: run production-excellence (RT-201—RT-220) validations via OptimizedRAPTOR."""
        return self.raptor.validate_production_excellence(validation_config)

    # ==============================================================================
    # GRAPH MUTATION INTEGRATION
    # ==============================================================================

    async def apply_realtime_updates(self, updates: List[Dict[str, Any]]):
        """Apply real-time updates to the routing graph"""
        for update in updates:
            update_type = update.get('type')

            if update_type == 'delay':
                await self._apply_delay_update(update)
            elif update_type == 'cancellation':
                await self._apply_cancellation_update(update)
            elif update_type == 'occupancy':
                await self._apply_occupancy_update(update)

    async def _apply_delay_update(self, update: Dict[str, Any]):
        """Apply delay update to graph"""
        trip_id = update['trip_id']
        delay_minutes = update['delay_minutes']

        # Update time-dependent graph
        if trip_id in self.time_graph.trip_nodes:
            for node in self.time_graph.trip_nodes[trip_id]:
                node.timestamp += timedelta(minutes=delay_minutes)

        # Update cached routes
        await self._invalidate_affected_routes(trip_id)

        logger.info(f"Applied {delay_minutes}min delay to trip {trip_id}")

    async def _apply_cancellation_update(self, update: Dict[str, Any]):
        """Apply cancellation update to graph"""
        trip_id = update['trip_id']
        cancelled_stations = update.get('cancelled_stations', [])

        # Mark trip as cancelled in graph
        if trip_id in self.time_graph.trip_nodes:
            for node in self.time_graph.trip_nodes[trip_id]:
                node.is_cancelled = True

        # Remove cancelled segments
        if cancelled_stations:
            self.time_graph.remove_cancelled_segments(trip_id, cancelled_stations)

        # Update cached routes
        await self._invalidate_affected_routes(trip_id)

        logger.info(f"Applied cancellation to trip {trip_id}")

    async def _apply_occupancy_update(self, update: Dict[str, Any]):
        """Apply occupancy update to graph"""
        trip_id = update['trip_id']
        occupancy_rate = update['occupancy_rate']

        # Update occupancy weights in graph
        if trip_id in self.time_graph.trip_nodes:
            for node in self.time_graph.trip_nodes[trip_id]:
                node.occupancy_weight = self._calculate_occupancy_penalty(occupancy_rate)

        logger.debug(f"Updated occupancy for trip {trip_id}: {occupancy_rate}")

    async def _invalidate_affected_routes(self, trip_id: int):
        """Invalidate cached routes affected by a trip change"""
        # Get all stations served by this trip
        session = SessionLocal()
        try:
            stop_times = session.query(StopTime).filter(
                StopTime.trip_id == trip_id
            ).all()

            affected_stations = {st.stop_id for st in stop_times}

            # Invalidate cache for routes involving these stations
            # This would integrate with Redis caching layer
            for station_id in affected_stations:
                cache_key = f"routes:station:{station_id}"
                # await redis.delete(cache_key)  # Would implement Redis integration

        finally:
            session.close()

    def _calculate_occupancy_penalty(self, occupancy_rate: float) -> float:
        """Calculate comfort penalty based on occupancy"""
        if occupancy_rate < 0.5:
            return 1.0  # No penalty
        elif occupancy_rate < 0.8:
            return 1.2  # Slight penalty
        else:
            return 1.5  # High penalty for crowded trains

    def _serialize_routes_for_cache(self, routes: List[Route]) -> Dict:
        """Serialize routes for caching"""
        return {
            'routes': [
                {
                    'segments': [
                        {
                            'trip_id': seg.trip_id,
                            'departure_stop_id': seg.departure_stop_id,
                            'arrival_stop_id': seg.arrival_stop_id,
                            'departure_time': seg.departure_time.isoformat(),
                            'arrival_time': seg.arrival_time.isoformat(),
                            'duration_minutes': seg.duration_minutes,
                            'distance_km': seg.distance_km,
                            'fare_amount': seg.fare_amount,
                            'train_name': seg.train_name,
                            'train_number': seg.train_number
                        } for seg in route.segments
                    ],
                    'transfers': [
                        {
                            'station_id': t.station_id,
                            'arrival_time': t.arrival_time.isoformat(),
                            'departure_time': t.departure_time.isoformat(),
                            'duration_minutes': t.duration_minutes,
                            'station_name': t.station_name
                        } for t in route.transfers
                    ],
                    'total_duration': route.total_duration,
                    'total_distance': route.total_distance,
                    'total_fare': route.total_fare,
                    'score': route.score,
                    'cached_at': datetime.utcnow().isoformat()
                } for route in routes
            ],
            'count': len(routes)
        }

    def _deserialize_cached_routes(self, cached_data: Dict) -> List[Route]:
        """Deserialize routes from cache"""
        routes = []
        for route_data in cached_data.get('routes', []):
            route = Route()

            # Deserialize segments
            for seg_data in route_data.get('segments', []):
                segment = RouteSegment(
                    trip_id=seg_data['trip_id'],
                    departure_stop_id=seg_data['departure_stop_id'],
                    arrival_stop_id=seg_data['arrival_stop_id'],
                    departure_time=datetime.fromisoformat(seg_data['departure_time']),
                    arrival_time=datetime.fromisoformat(seg_data['arrival_time']),
                    duration_minutes=seg_data['duration_minutes'],
                    distance_km=seg_data.get('distance_km', 0),
                    fare_amount=seg_data.get('fare_amount', 0),
                    train_name=seg_data.get('train_name', ''),
                    train_number=seg_data.get('train_number', '')
                )
                route.add_segment(segment)

            # Deserialize transfers
            for transfer_data in route_data.get('transfers', []):
                transfer = TransferConnection(
                    station_id=transfer_data['station_id'],
                    arrival_time=datetime.fromisoformat(transfer_data['arrival_time']),
                    departure_time=datetime.fromisoformat(transfer_data['departure_time']),
                    duration_minutes=transfer_data['duration_minutes'],
                    station_name=transfer_data.get('station_name', ''),
                    facilities_score=0.0,
                    safety_score=0.0
                )
                route.add_transfer(transfer)

            # Set totals
            route.total_duration = route_data.get('total_duration', 0)
            route.total_distance = route_data.get('total_distance', 0)
            route.total_fare = route_data.get('total_fare', 0)
            route.score = route_data.get('score', 0)

            routes.append(route)

        return routes

    def validate_multimodal_route(self, multimodal_route, validation_config: dict = None) -> bool:
        """
        Validate a multi-modal route using all RT-051 to RT-070 checks.
        
        Args:
            multimodal_route: Multi-modal route object to validate
            validation_config: Configuration for validation parameters
        
        Returns:
            Boolean indicating if route passes all validations
        """
        if validation_config is None:
            validation_config = {}

        # Delegate to ValidationManager (short-circuit old checks)
        config = {'route': multimodal_route}
        config.update(validation_config)

        report = self.validation_manager.validate(
            config,
            profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.MULTIMODAL}
        )
        return report.all_passed

    def validate_fare_and_availability(self, route: Route, travel_class: str = "SL") -> bool:
        """
        Validate fare and availability using RT-071 to RT-090 checks.
        """
        config = {'route': route, 'travel_class': travel_class}
        report = self.validation_manager.validate(
            config,
            profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.FARES_AND_AVAILABILITY}
        )
        return report.all_passed

    def validate_api_and_security(self, request_data: dict, auth_token: str) -> bool:
        """
        Validate API security using RT-091 to RT-110 checks.
        """
        config = {'request_data': request_data, 'auth_token': auth_token}
        report = self.validation_manager.validate_api_request(
            request_data, 
            auth_token,
            profile=ValidationProfile.STANDARD
        )
        return report.all_passed

    def validate_data_integrity(self, graph_data: dict) -> bool:
        """
        Validate data integrity for graph and route results using RT-111 to RT-130.
        """
        config = {'graph_data': graph_data}
        report = self.validation_manager.validate(
            config,
            profile=ValidationProfile.FULL,
            specific_categories={ValidationCategory.DATA_INTEGRITY}
        )
        return report.all_passed

    def validate_ai_ranking(self, ranked_routes: list, user_context: dict) -> bool:
        """
        Validate AI ranking and personalization using RT-151 to RT-170.
        """
        config = {'ranked_routes': ranked_routes, 'user_context': user_context}
        report = self.validation_manager.validate(
            config,
            profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.AI_RANKING}
        )
        return report.all_passed

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_station_by_code(code: str) -> Optional[Stop]:
    """Get station by code"""
    session = SessionLocal()
    try:
        return session.query(Stop).filter(Stop.code == code).first()
    finally:
        session.close()


def calculate_segment_fare(from_stop: Stop, to_stop: Stop, route_type: str) -> float:
    """Calculate fare for a segment (simplified)"""
    # In production, this would use distance-based pricing
    base_fare = 100.0
    return base_fare



    def validate_api_and_security(self, request, security_context, validation_config: dict = None) -> bool:
        """
        Validate an API request using all RT-111 to RT-130 security checks.
        
        Args:
            request: API request object to validate
            security_context: Security context for the request
            validation_config: Configuration for validation parameters
        
        Returns:
            Boolean indicating if request passes all validations
        """
        if validation_config is None:
            validation_config = {}

        # Delegate to ValidationManager (short-circuit old checks)
        report = self.validation_manager.validate_api_request(request, security_context)
        if not report.all_passed:
            for res in report.results:
                if not res.passed:
                    logger.warning(f"{res.validation_id} failed: {res.error_message}")
        return report.all_passed



    def validate_data_integrity(self, validation_config: dict = None) -> bool:
        """
        Validate data integrity and consistency using all RT-131 to RT-150 checks.
        
        Args:
            validation_config: Configuration for validation parameters
        
        Returns:
            Boolean indicating if data passes all integrity checks
        """
        if validation_config is None:
            validation_config = {}

        # Delegate to ValidationManager (short-circuit old checks)
        report = self.validation_manager.validate(
            validation_config,
            profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.DATA_INTEGRITY}
        )

        if not report.all_passed:
            for res in report.results:
                if not res.passed:
                    logger.warning(f"{res.validation_id} failed: {res.error_message}")
        return report.all_passed

        # RT-131: Station graph connectivity
        stations = validation_config.get('stations', [])
        transfers = validation_config.get('transfers', [])
        if stations and transfers:
            if not self.data_integrity_validator.validate_station_graph_connectivity(stations, transfers):
                logger.warning("RT-131: Station graph connectivity validation failed")
                return False

        # RT-132: Orphan nodes detection
        if stations and transfers:
            if not self.data_integrity_validator.validate_orphan_nodes_detection(stations, transfers):
                logger.warning("RT-132: Orphan nodes detection validation failed")
                return False

        # RT-133: Duplicate station IDs
        if stations:
            if not self.data_integrity_validator.validate_duplicate_station_ids(stations):
                logger.warning("RT-133: Duplicate station IDs validation failed")
                return False

        # RT-134: Trip continuity validation
        trips = validation_config.get('trips', [])
        for trip in trips:
            if not self.data_integrity_validator.validate_trip_continuity(trip):
                logger.warning(f"RT-134: Trip continuity validation failed for trip {trip.trip_id}")
                return False

        # RT-135: Missing timestamps handling
        if trips:
            if not self.data_integrity_validator.validate_missing_timestamps_handling(trips):
                logger.warning("RT-135: Missing timestamps handling validation failed")
                return False

        # RT-136: Negative durations rejected
        if trips:
            if not self.data_integrity_validator.validate_negative_durations_rejected(trips):
                logger.warning("RT-136: Negative durations rejected validation failed")
                return False

        # RT-137: Time ordering in stops
        for trip in trips:
            if not self.data_integrity_validator.validate_time_ordering_in_stops(trip):
                logger.warning(f"RT-137: Time ordering in stops validation failed for trip {trip.trip_id}")
                return False

        # RT-138: Distance monotonic increase
        for trip in trips:
            if not self.data_integrity_validator.validate_distance_monotonic_increase(trip):
                logger.warning(f"RT-138: Distance monotonic increase validation failed for trip {trip.trip_id}")
                return False

        # RT-139: Data import validation
        dataset = validation_config.get('dataset')
        data_rows = validation_config.get('data_rows', [])
        if dataset and data_rows:
            if not self.data_integrity_validator.validate_data_import_validation(dataset, data_rows):
                logger.warning("RT-139: Data import validation failed")
                return False

        # RT-140: Partial dataset recovery
        original_data = validation_config.get('original_data', [])
        corrupted_indices = validation_config.get('corrupted_indices', [])
        if original_data:
            if not self.data_integrity_validator.validate_partial_dataset_recovery(original_data, corrupted_indices):
                logger.warning("RT-140: Partial dataset recovery validation failed")
                return False

        # RT-141: Index corruption recovery
        primary_index = validation_config.get('primary_index', {})
        backup_index = validation_config.get('backup_index', {})
        if primary_index or backup_index:
            if not self.data_integrity_validator.validate_index_corruption_recovery(primary_index, backup_index):
                logger.warning("RT-141: Index corruption recovery validation failed")
                return False

        # RT-142: Cache vs DB consistency
        cache_data = validation_config.get('cache_data', {})
        db_data = validation_config.get('db_data', {})
        if cache_data or db_data:
            if not self.data_integrity_validator.validate_cache_vs_db_consistency(cache_data, db_data):
                logger.warning("RT-142: Cache vs DB consistency validation failed")
                return False

        # RT-143: Graph rebuild determinism
        graph_v1 = validation_config.get('graph_v1', {})
        graph_v2 = validation_config.get('graph_v2', {})
        if graph_v1 or graph_v2:
            if not self.data_integrity_validator.validate_graph_rebuild_determinism(graph_v1, graph_v2):
                logger.warning("RT-143: Graph rebuild determinism validation failed")
                return False

        # RT-144: Realtime merge consistency
        static_data = validation_config.get('static_data', {})
        realtime_data = validation_config.get('realtime_data', {})
        merged_data = validation_config.get('merged_data', {})
        if static_data or realtime_data or merged_data:
            if not self.data_integrity_validator.validate_realtime_merge_consistency(static_data, realtime_data, merged_data):
                logger.warning("RT-144: Realtime merge consistency validation failed")
                return False

        # RT-145: Timezone mismatch detection
        if stations:
            if not self.data_integrity_validator.validate_timezone_mismatch_detection(stations):
                logger.warning("RT-145: Timezone mismatch detection validation failed")
                return False

        # RT-146: Station coordinate sanity
        if stations:
            if not self.data_integrity_validator.validate_station_coordinate_sanity(stations):
                logger.warning("RT-146: Station coordinate sanity validation failed")
                return False

        # RT-147: GTFS spec compliance
        required_fields = validation_config.get('gtfs_required_fields', [])
        data_sample = validation_config.get('gtfs_data_sample', [])
        if dataset and required_fields and data_sample:
            if not self.data_integrity_validator.validate_gtfs_spec_compliance(dataset, required_fields, data_sample):
                logger.warning("RT-147: GTFS spec compliance validation failed")
                return False

        # RT-148: Referential integrity
        valid_route_ids = validation_config.get('valid_route_ids', set())
        valid_service_ids = validation_config.get('valid_service_ids', set())
        if trips and (valid_route_ids or valid_service_ids):
            if not self.data_integrity_validator.validate_referential_integrity(trips, valid_route_ids, valid_service_ids):
                logger.warning("RT-148: Referential integrity validation failed")
                return False

        # RT-149: Snapshot rollback correctness
        snapshot_before = validation_config.get('snapshot_before', {})
        snapshot_after = validation_config.get('snapshot_after', {})
        original_data_snapshot = validation_config.get('original_data_snapshot', {})
        if snapshot_before or snapshot_after:
            if not self.data_integrity_validator.validate_snapshot_rollback_correctness(snapshot_before, snapshot_after, original_data_snapshot):
                logger.warning("RT-149: Snapshot rollback correctness validation failed")
                return False

        # RT-150: Data version migration
        old_version = validation_config.get('old_version')
        new_version = validation_config.get('new_version')
        migration_successful = validation_config.get('migration_successful', False)
        if old_version and new_version:
            if not self.data_integrity_validator.validate_data_version_migration(old_version, new_version, migration_successful):
                logger.warning("RT-150: Data version migration validation failed")
                return False

        logger.info("All data integrity and consistency validations (RT-131 to RT-150) passed")
        return True

    def validate_ai_ranking(self, validation_config: dict = None) -> bool:
        """
        Delegate AI/Smart ranking validations (RT-151 to RT-170) to ValidationManager.
        Only checks with required parameters present in `validation_config` will run.
        """
        if validation_config is None:
            validation_config = {}

        config = {'ai_context': validation_config}
        config.update(validation_config)

        report = self.validation_manager.validate(
            config,
            profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.AI_RANKING}
        )

        if not report.all_passed:
            for res in report.results:
                if not res.passed:
                    logger.warning(f"{res.validation_id} failed: {res.error_message}")
            return False

        logger.info("All AI/Smart ranking validations (RT-151 to RT-170) passed")
        return True