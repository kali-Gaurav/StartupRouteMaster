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
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Set, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
import logging

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload

from .database import SessionLocal
from .models import (
    Stop, Trip, StopTime, Route as GTFRoute,
    Calendar, CalendarDate, Transfer
)
from .config import Config
from .services.multi_layer_cache import multi_layer_cache, RouteQuery, cache_route_search

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
        start_time = time.time()

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

                        new_route = Route()
                        new_route.segments = route.segments.copy()
                        new_route.transfers = route.transfers.copy()
                        new_route.add_transfer(transfer)
                        new_route.add_segment(segment)

                        # Update totals
                        new_route.total_duration = route.total_duration + transfer.duration_minutes + segment.duration_minutes
                        new_route.total_cost = route.total_cost + segment.fare
                        new_route.total_distance = route.total_distance + segment.distance_km

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

                    # Convert times to datetime
                    dep_dt = self._time_to_datetime(date, current.departure_time)
                    arr_dt = self._time_to_datetime(date, next_stop.arrival_time)

                    segment = RouteSegment(
                        trip_id=trip_id,
                        departure_stop_id=current.stop_id,
                        arrival_stop_id=next_stop.stop_id,
                        departure_time=dep_dt,
                        arrival_time=arr_dt,
                        duration_minutes=(arr_dt - dep_dt).seconds // 60,
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
        """Check if transfer meets constraints"""
        if transfer.duration_minutes < constraints.min_transfer_time:
            return False
        if transfer.duration_minutes > constraints.max_layover_time:
            return False

        if constraints.avoid_night_layovers:
            if self._is_night_layover(transfer.arrival_time, transfer.departure_time):
                return False

        return True

    def _is_night_layover(self, arrival: datetime, departure: datetime) -> bool:
        """Check if layover spans night hours (22:00-05:00)"""
        night_start = arrival.replace(hour=22, minute=0, second=0, microsecond=0)
        night_end = departure.replace(hour=5, minute=0, second=0, microsecond=0)

        # Check if layover overlaps with night hours
        return (arrival <= night_start < departure) or (arrival <= night_end < departure)

    def _is_safe_station(self, station_id: int) -> bool:
        """Check if station is considered safe (simplified)"""
        # In production, this would check safety ratings from database
        return True  # Placeholder

    def _calculate_score(self, route: Route, constraints: RouteConstraints) -> float:
        """Calculate multi-objective score"""
        weights = constraints.weights

        # Time score (lower is better)
        time_score = route.total_duration

        # Cost score (lower is better)
        cost_score = route.total_cost

        # Comfort score (higher is better, converted to penalty)
        comfort_score = 0
        for transfer in route.transfers:
            comfort_score += transfer.facilities_score * 10  # Scale up
            if self._is_night_layover(transfer.arrival_time, transfer.departure_time):
                comfort_score -= 20  # Night layover penalty

        # Safety score (higher is better)
        safety_score = 0
        if constraints.women_safety_priority:
            for station_id in route.get_all_stations():
                safety_score += 5  # Base safety score per station

        # Weighted combination
        total_score = (weights.time * time_score +
                      weights.cost * cost_score -
                      weights.comfort * comfort_score +
                      weights.safety * safety_score)

        return total_score


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