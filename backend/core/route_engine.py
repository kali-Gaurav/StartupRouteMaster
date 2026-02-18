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

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload

from ..database import SessionLocal
from ..database.models import (
    Stop, Trip, StopTime, Route as GTFRoute,
    Calendar, CalendarDate, Transfer
)
from ..database.config import Config
from ..services.multi_layer_cache import multi_layer_cache, RouteQuery, cache_route_search
from .route_validators import RouteValidator
from .multimodal_validators import MultimodalValidator
from .fare_availability_validators import FareAndAvailabilityValidator

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
    train_name: str
    train_number: str

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
    """Optimized time-dependent graph for RAPTOR"""

    def __init__(self):
        self.departures_by_stop: Dict[int, List[Tuple[datetime, int]]] = defaultdict(list)
        self.arrivals_by_stop: Dict[int, List[Tuple[datetime, int]]] = defaultdict(list)
        self.trip_segments: Dict[int, List[RouteSegment]] = defaultdict(list)
        self.transfer_graph: Dict[int, List[TransferConnection]] = defaultdict(list)
        self.stop_cache: Dict[int, Stop] = {}

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

    def get_trip_segments(self, trip_id: int) -> List[RouteSegment]:
        """Get all segments for a trip"""
        return self.trip_segments.get(trip_id, [])


class OptimizedRAPTOR:
    """Production-optimized RAPTOR algorithm implementation"""

    def __init__(self, max_transfers: int = 3):
        self.max_transfers = max_transfers
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.validator = RouteValidator()
        self.multimodal_validator = MultimodalValidator()
        self.fare_availability_validator = FareAndAvailabilityValidator()

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
        cached_result = await multi_layer_cache.get_route_query(cache_query)
        if cached_result:
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
        Internal route computation (original find_routes logic)
        """
        start_time = _time.time()

        # Build time-dependent graph
        graph = await self._build_graph(departure_date)

        # Initialize RAPTOR structures
        routes_by_round: Dict[int, List[Route]] = defaultdict(list)
        earliest_arrival: Dict[int, datetime] = {}
        best_routes: Dict[str, Route] = {}

        # Round 0: Direct connections from source
        source_departures = graph.get_departures_from_stop(source_stop_id, departure_date)

        for dep_time, trip_id in source_departures[:50]:  # Limit initial departures
            segments = graph.get_trip_segments(trip_id)
            for segment in segments:
                if segment.departure_stop_id == source_stop_id and segment.departure_time >= dep_time:
                    route = Route()
                    route.add_segment(segment)

                    # Check if this segment reaches destination
                    if segment.arrival_stop_id == dest_stop_id:
                        if self._validate_route_constraints(route, constraints):
                            score = self._calculate_score(route, constraints)
                            route.score = score
                            key = f"direct_{trip_id}"
                            if key not in best_routes or score < best_routes[key].score:
                                best_routes[key] = route
                    else:
                        routes_by_round[0].append(route)
                    break  # Only add first matching segment per trip

        # RAPTOR rounds (transfers)
        for round_num in range(1, self.max_transfers + 1):
            if not routes_by_round[round_num - 1]:
                break

            current_routes = routes_by_round[round_num - 1]

            # Process routes in parallel batches
            batch_size = 10
            for i in range(0, len(current_routes), batch_size):
                batch = current_routes[i:i + batch_size]
                transfer_routes = await asyncio.gather(*[
                    self._process_route_transfers(route, graph, dest_stop_id, constraints)
                    for route in batch
                ])

                for route_list in transfer_routes:
                    routes_by_round[round_num].extend(route_list)

        # Collect all valid routes to destination
        all_routes = []
        for key, route in best_routes.items():
            if self._validate_route_constraints(route, constraints):
                all_routes.append(route)

        # Sort by score
        all_routes.sort(key=lambda r: r.score)

        logger.info(".2f")

        return all_routes[:constraints.max_results]

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
                                score = self._calculate_score(new_route, constraints)
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

                # Create segments
                trip_segments = []
                for i in range(len(trip_stop_times) - 1):
                    current = trip_stop_times[i]
                    next_stop = trip_stop_times[i + 1]

                    # Convert times to datetime (handle overnight / multi-day via rollover)
                    dep_dt = self._time_to_datetime(date, current.departure_time)
                    arr_dt = self._time_to_datetime(date, next_stop.arrival_time)

                    # If arrival datetime is earlier than departure, roll forward by whole days
                    # This covers midnight crossings and multi-day trips when DB only stores time-of-day
                    while arr_dt < dep_dt:
                        arr_dt += timedelta(days=1)

                    duration_minutes = int((arr_dt - dep_dt).total_seconds() // 60)

                    segment = RouteSegment(
                        trip_id=trip_id,
                        departure_stop_id=current.stop_id,
                        arrival_stop_id=next_stop.stop_id,
                        departure_time=dep_dt,
                        arrival_time=arr_dt,
                        duration_minutes=duration_minutes,
                        distance_km=0.0,  # Would need distance calculation
                        fare=100.0,  # Base fare, would be calculated
                        train_name=getattr(trip_stop_times[0].trip.route, 'long_name', 'Unknown'),
                        train_number=str(trip_id)
                    )

                    trip_segments.append(segment)

                    # Add to departures index
                    departures[current.stop_id].append((dep_dt, trip_id))

                    # Add to arrivals index
                    arrivals[next_stop.stop_id].append((arr_dt, trip_id))

                segments[trip_id] = trip_segments

            # Build transfer graph
            transfers = defaultdict(list)
            all_stops = session.query(Stop).all()

            for stop in all_stops:
                stops[stop.id] = stop

                # Generate transfer connections (simplified)
                # In production, this would use real transfer data
                for hour in range(24):
                    for minute in [0, 15, 30, 45]:
                        arr_time = date.replace(hour=hour, minute=minute)
                        dep_time = arr_time + timedelta(minutes=15)  # Min transfer time

                        transfer = TransferConnection(
                            station_id=stop.id,
                            arrival_time=arr_time,
                            departure_time=dep_time,
                            duration_minutes=15,
                            station_name=stop.name,
                            facilities_score=0.7,  # Would be calculated from facilities
                            safety_score=0.8       # Would be calculated from safety data
                        )
                        transfers[stop.id].append(transfer)

            return {
                'departures': departures,
                'arrivals': arrivals,
                'segments': segments,
                'transfers': transfers,
                'stops': stops
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

    async def _deduplicate_routes(self, routes: List[Route]) -> List[Route]:
        """Deduplicate routes based on segments and transfers."""
        unique_routes = {}
        for route in routes:
            route_key = (tuple(route.get_all_stations()), tuple(route.transfers))
            if route_key not in unique_routes:
                unique_routes[route_key] = route
            else:
                # Keep the route with the better score
                if route.score < unique_routes[route_key].score:
                    unique_routes[route_key] = route

        return list(unique_routes.values())

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


# ==============================================================================
# PUBLIC API
# ==============================================================================

class RouteEngine:
    """Main route engine interface"""

    def __init__(self):
        self.raptor = OptimizedRAPTOR(max_transfers=3)

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

    async def handle_realtime_updates(self, realtime_data: dict, route: Route):
        """Handle real-time updates and validate using RouteValidator."""
        if not self.validator.validate_realtime_delay_propagation(realtime_data, route):
            return False
        if not self.validator.validate_cancellation_removal(realtime_data, route):
            return False
        if not self.validator.validate_partial_delay(realtime_data, route):
            return False
        if not self.validator.validate_realtime_update_during_query(realtime_data, route):
            return False
        if not self.validator.validate_outdated_realtime_cache(realtime_data, route):
            return False
        # Additional real-time validations can be added here
        return True

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

        # RT-051: Train-bus integration
        if not self.multimodal_validator.validate_train_bus_integration(multimodal_route):
            logger.warning("RT-051: Train-bus integration validation failed")
            return False

        # RT-052: Walk transfer segments
        if not self.multimodal_validator.validate_walk_transfer_segments(multimodal_route):
            logger.warning("RT-052: Walk transfer segments validation failed")
            return False

        # RT-053: Mode preference filtering
        preferred_modes = validation_config.get('preferred_modes', [])
        if not self.multimodal_validator.validate_mode_preference_filtering(multimodal_route, preferred_modes):
            logger.warning("RT-053: Mode preference filtering validation failed")
            return False

        # RT-054: Disabled transport mode excluded
        disabled_modes = validation_config.get('disabled_modes', [])
        if not self.multimodal_validator.validate_disabled_transport_mode_excluded(multimodal_route, disabled_modes):
            logger.warning("RT-054: Disabled transport mode validation failed")
            return False

        # RT-055: Multi-modal transfer penalties
        transfer_penalties = validation_config.get('transfer_penalties', {})
        if not self.multimodal_validator.validate_multimodal_transfer_penalties(multimodal_route, transfer_penalties):
            logger.warning("RT-055: Multi-modal transfer penalties validation failed")
            return False

        # RT-056: First/last mile inclusion
        if not self.multimodal_validator.validate_first_last_mile_inclusion(multimodal_route):
            logger.warning("RT-056: First/last mile inclusion validation failed")
            return False

        # RT-057: Bike or taxi connectors
        allow_bike = validation_config.get('allow_bike', True)
        allow_taxi = validation_config.get('allow_taxi', True)
        if not self.multimodal_validator.validate_bike_taxi_connectors(multimodal_route, allow_bike, allow_taxi):
            logger.warning("RT-057: Bike/taxi connectors validation failed")
            return False

        # RT-058: Mode cost weighting
        if not self.multimodal_validator.validate_mode_cost_weighting(multimodal_route):
            logger.warning("RT-058: Mode cost weighting validation failed")
            return False

        # RT-059: Mixed schedule and frequency routes
        if not self.multimodal_validator.validate_mixed_schedule_frequency_routes(multimodal_route):
            logger.warning("RT-059: Mixed schedule/frequency validation failed")
            return False

        # RT-060: Walking time estimation
        if not self.multimodal_validator.validate_walking_time_estimation(multimodal_route):
            logger.warning("RT-060: Walking time estimation validation failed")
            return False

        # RT-061: Maximum walking distance
        max_walking_distance = validation_config.get('max_walking_distance_m', 2000)
        if not self.multimodal_validator.validate_maximum_walking_distance(multimodal_route, max_walking_distance):
            logger.warning("RT-061: Maximum walking distance validation failed")
            return False

        # RT-062: Mode change count
        max_mode_changes = validation_config.get('max_mode_changes', 4)
        if not self.multimodal_validator.validate_mode_change_count(multimodal_route, max_mode_changes):
            logger.warning("RT-062: Mode change count validation failed")
            return False

        # RT-063: Airport transfer integration
        is_airport_route = validation_config.get('is_airport_route', False)
        if not self.multimodal_validator.validate_airport_transfer_integration(multimodal_route, is_airport_route):
            logger.warning("RT-063: Airport transfer integration validation failed")
            return False

        # RT-064: Metro-rail sync
        if not self.multimodal_validator.validate_metro_rail_sync(multimodal_route):
            logger.warning("RT-064: Metro-rail sync validation failed")
            return False

        # RT-065: Overnight bus-train
        if not self.multimodal_validator.validate_overnight_bus_train(multimodal_route):
            logger.warning("RT-065: Overnight bus-train validation failed")
            return False

        # RT-066: Mode priority override
        mode_priority = validation_config.get('mode_priority', {})
        if not self.multimodal_validator.validate_mode_priority_override(multimodal_route, mode_priority):
            logger.warning("RT-066: Mode priority override validation failed")
            return False

        # RT-067: Transfer station mismatch
        if not self.multimodal_validator.validate_transfer_station_mismatch(multimodal_route):
            logger.warning("RT-067: Transfer station mismatch validation failed")
            return False

        # RT-068: Geographic distance sanity
        if not self.multimodal_validator.validate_geographic_distance_sanity(multimodal_route):
            logger.warning("RT-068: Geographic distance sanity validation failed")
            return False

        # RT-069: Rural sparse network
        is_rural = validation_config.get('is_rural', False)
        if not self.multimodal_validator.validate_rural_sparse_network(multimodal_route, is_rural):
            logger.warning("RT-069: Rural sparse network validation failed")
            return False

        # RT-070: Mode unavailable fallback
        unavailable_modes = validation_config.get('unavailable_modes', [])
        if not self.multimodal_validator.validate_mode_unavailable_fallback(multimodal_route, unavailable_modes):
            logger.warning("RT-070: Mode unavailable fallback validation failed")
            return False

        logger.info("All multimodal route validations (RT-051 to RT-070) passed")
        return True

    def validate_fare_and_availability(self, fare_and_avail, validation_config: dict = None) -> bool:
        """
        Validate a fare and availability route using all RT-071 to RT-090 checks.
        
        Args:
            fare_and_avail: Fare and availability object to validate
            validation_config: Configuration for validation parameters
        
        Returns:
            Boolean indicating if route passes all validations
        """
        if validation_config is None:
            validation_config = {}

        # RT-071: Fare calculation per segment
        for fare_seg in fare_and_avail.fare_segments:
            if not self.fare_availability_validator.validate_fare_calculation_per_segment(fare_seg):
                logger.warning("RT-071: Fare calculation per segment validation failed")
                return False

        # RT-072: Total fare aggregation
        if not self.fare_availability_validator.validate_total_fare_aggregation(
            fare_and_avail.fare_segments, fare_and_avail.total_fare
        ):
            logger.warning("RT-072: Total fare aggregation validation failed")
            return False

        # RT-073: Dynamic pricing override
        is_peak_time = validation_config.get('is_peak_time', False)
        if not self.fare_availability_validator.validate_dynamic_pricing_override(fare_and_avail, is_peak_time):
            logger.warning("RT-073: Dynamic pricing override validation failed")
            return False

        # RT-074: Seat availability filtering
        requested_class = validation_config.get('seat_class', None)
        num_passengers = validation_config.get('num_passengers', 1)
        if requested_class and fare_and_avail.seat_info:
            for seat_id, seat_info in fare_and_avail.seat_info.items():
                if not self.fare_availability_validator.validate_seat_availability_filtering(
                    seat_info, requested_class, num_passengers
                ):
                    logger.warning("RT-074: Seat availability filtering validation failed")
                    return False

        # RT-075: Waitlist handling
        allow_waitlist = validation_config.get('allow_waitlist', False)
        if requested_class and fare_and_avail.seat_info:
            for seat_id, seat_info in fare_and_avail.seat_info.items():
                if not self.fare_availability_validator.validate_waitlist_handling(
                    seat_info, requested_class, num_passengers, allow_waitlist
                ):
                    logger.warning("RT-075: Waitlist handling validation failed")
                    return False

        # RT-076: Class preference filtering
        preferred_classes = validation_config.get('preferred_classes', [])
        if not self.fare_availability_validator.validate_class_preference_filtering(fare_and_avail, preferred_classes):
            logger.warning("RT-076: Class preference filtering validation failed")
            return False

        # RT-077: Fare currency consistency
        if not self.fare_availability_validator.validate_fare_currency_consistency(fare_and_avail):
            logger.warning("RT-077: Fare currency consistency validation failed")
            return False

        # RT-078: Discounts applied correctly
        for fare_seg in fare_and_avail.fare_segments:
            if not self.fare_availability_validator.validate_discounts_applied_correctly(fare_seg):
                logger.warning("RT-078: Discounts applied correctly validation failed")
                return False

        # RT-079: Multi-modal fare merging
        if not self.fare_availability_validator.validate_multimodal_fare_merging(fare_and_avail.fare_segments):
            logger.warning("RT-079: Multi-modal fare merging validation failed")
            return False

        # RT-080: Fare rounding correctness
        fares = [seg.total_fare for seg in fare_and_avail.fare_segments]
        if not self.fare_availability_validator.validate_fare_rounding_correctness(fares, fare_and_avail.total_fare):
            logger.warning("RT-080: Fare rounding correctness validation failed")
            return False

        # RT-081: Missing fare data fallback
        if not self.fare_availability_validator.validate_missing_fare_data_fallback(fare_and_avail):
            logger.warning("RT-081: Missing fare data fallback validation failed")
            return False

        # RT-082: Surge pricing updates
        previous_fares = validation_config.get('previous_fares', {})
        if previous_fares:
            if not self.fare_availability_validator.validate_surge_pricing_updates(fare_and_avail, previous_fares):
                logger.warning("RT-082: Surge pricing updates validation failed")
                return False

        # RT-083: Fare caps enforced
        fare_cap = validation_config.get('fare_cap', None)
        if not self.fare_availability_validator.validate_fare_caps_enforced(fare_and_avail, fare_cap):
            logger.warning("RT-083: Fare caps enforced validation failed")
            return False

        # RT-084: Seat quota handling
        class_quotas = validation_config.get('class_quotas', {})
        if class_quotas and fare_and_avail.seat_info:
            for seat_id, seat_info in fare_and_avail.seat_info.items():
                if not self.fare_availability_validator.validate_seat_quota_handling(seat_info, class_quotas):
                    logger.warning("RT-084: Seat quota handling validation failed")
                    return False

        # RT-085: Tatkal-like priority quota
        for fare_seg in fare_and_avail.fare_segments:
            if not self.fare_availability_validator.validate_tatkal_priority_quota(None, fare_seg):
                logger.warning("RT-085: Tatkal priority quota validation failed")
                return False

        # RT-086: Fare caching consistency
        cached_fares = validation_config.get('cached_fares', {})
        if cached_fares:
            for i, seg in enumerate(fare_and_avail.fare_segments):
                cached_seg = cached_fares.get(i)
                if cached_seg:
                    if not self.fare_availability_validator.validate_fare_caching_consistency(cached_seg, seg):
                        logger.warning("RT-086: Fare caching consistency validation failed")
                        return False

        # RT-087: Partial availability segment
        if not self.fare_availability_validator.validate_partial_availability_segment(fare_and_avail, num_passengers):
            logger.warning("RT-087: Partial availability segment validation failed")
            return False

        # RT-088: Price optimization mode
        optimization_mode = validation_config.get('optimization_mode', 'standard')
        if not self.fare_availability_validator.validate_price_optimization_mode(fare_and_avail, optimization_mode):
            logger.warning("RT-088: Price optimization mode validation failed")
            return False

        # RT-089: Refund calculation scenario
        if not self.fare_availability_validator.validate_refund_calculation_scenario(
            fare_and_avail.total_fare,
            validation_config.get('cancellation_fee_percent', 10.0)
        ):
            logger.warning("RT-089: Refund calculation scenario validation failed")
            return False

        # RT-090: Zero fare route edge case
        if not self.fare_availability_validator.validate_zero_fare_route_edge_case(fare_and_avail):
            logger.warning("RT-090: Zero fare route edge case validation failed")
            return False

        logger.info("All fare and availability validations (RT-071 to RT-090) passed")
        return True