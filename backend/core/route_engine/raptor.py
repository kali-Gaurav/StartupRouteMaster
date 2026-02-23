import asyncio
import logging
import time as _time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple

from ...database import SessionLocal
from ...database.models import Stop, StopTime, TrainState
from ...services.multi_layer_cache import multi_layer_cache, RouteQuery
from ...ml_reliability_model import get_reliability_model
from ...frequency_aware_range import get_frequency_aware_sizer
from ...utils.graph_utils import haversine_distance

from ..validator.performance_validators import PerformanceValidator
from ..validator.validation_manager import create_validation_manager_with_defaults, ValidationProfile, ValidationCategory

from .data_structures import Route, RouteSegment, TransferConnection, UserContext
from .constraints import RouteConstraints
from .graph import TimeDependentGraph, StaticGraphSnapshot
from .builder import GraphBuilder
from .hub import HubManager, HubConnectivityTable
from .snapshot_manager import SnapshotManager
from .transfer_intelligence import TransferIntelligenceManager # New import
from ...services.ml.capacity_models import CapacityPredictionModel # Phase 8

logger = logging.getLogger(__name__)

class OptimizedRAPTOR:
    """Production-optimized RAPTOR algorithm implementation"""

    def __init__(self, max_transfers: int = 3, validation_manager=None, 
                 graph_builder: Optional[GraphBuilder] = None, 
                 snapshot_manager: Optional[SnapshotManager] = None):
        self.max_transfers = max_transfers
        self.executor = ThreadPoolExecutor(max_workers=4)
        # Keep the performance validator locally (used for timing checks in the engine)
        self.performance_validator = PerformanceValidator()
        # Use ValidationManager to orchestrate all other validation logic
        self.validation_manager = validation_manager or create_validation_manager_with_defaults()
        
        # Injected dependencies for graph management
        self.graph_builder = graph_builder or GraphBuilder(self.executor)
        self.snapshot_manager = snapshot_manager or SnapshotManager()
        
        # Phase 4: Transfer Intelligence Manager
        self.transfer_intelligence_manager = TransferIntelligenceManager(SessionLocal)
        
        # Phase 8: Capacity Prediction
        self.capacity_model = CapacityPredictionModel()

    async def find_routes(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: Optional[TimeDependentGraph] = None) -> List[Route]:
        """
        Find multi-transfer routes using optimized RAPTOR algorithm with caching

        Args:
            source_stop_id: Source station ID
            dest_stop_id: Destination station ID
            departure_date: Journey date
            constraints: Route constraints and weights
            graph: Optional pre-built graph to use (expected from RailwayRouteEngine)

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
        cache_start = _time.time()
        cached_result = await multi_layer_cache.get_route_query(cache_query)
        cache_elapsed_ms = (_time.time() - cache_start) * 1000.0
        if cached_result:
            if not self.performance_validator.validate_cache_hit_performance(cache_elapsed_ms, expected_max_ms=50.0):
                logger.warning("RT-093: cache-hit latency exceeded threshold (%.2fms)", cache_elapsed_ms)
            logger.info(f"Route cache hit for {source_stop_id} -> {dest_stop_id}")
            return self._deserialize_cached_routes(cached_result)

        # Compute routes
        routes = await self._compute_routes(source_stop_id, dest_stop_id, departure_date, constraints, graph)

        # Cache the result
        if routes:
            serialized_routes = self._serialize_routes_for_cache(routes)
            await multi_layer_cache.set_route_query(cache_query, serialized_routes)

        return routes

    async def _compute_routes(self, source_stop_id: int, dest_stop_id: int,
                             departure_date: datetime, constraints: RouteConstraints,
                             graph: Optional[TimeDependentGraph] = None) -> List[Route]:
        """
        Internal route computation with frequency-aware Range-RAPTOR.
        This method is now primarily used by the main engine, which provides the graph.
        For internal calls (e.g., HubManager precomputation), it might build its own graph.
        """
        start_time = _time.time()

        # Build time-dependent graph if not provided
        if graph is None:
            graph_build_start = _time.time()
            # Attempt to load from snapshot first
            snapshot = await self.snapshot_manager.load_snapshot(departure_date)
            if snapshot:
                graph = TimeDependentGraph(snapshot=snapshot)
                logger.info(f"Loaded graph from snapshot for {departure_date.date()}")
            else:
                graph = await self.graph_builder.build_graph(departure_date)
                logger.info(f"Built graph from database for {departure_date.date()}")
            
            graph_build_ms = (_time.time() - graph_build_start) * 1000.0
            if not self.performance_validator.validate_graph_rebuild_performance(graph_build_ms, threshold_ms=1500.0):
                logger.warning("RT-096: graph rebuild time high (%.2fms)", graph_build_ms)

        # If graph is still None, something is wrong
        if graph is None:
            raise RuntimeError("TimeDependentGraph could not be loaded or built.")


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

    async def _search_single_departure(self, graph: TimeDependentGraph, source_stop_id: int, dest_stop_id: int,
                                      departure_dt: datetime, constraints: RouteConstraints) -> List[Route]:
        """Single-departure RAPTOR search that reuses an already-built graph."""
        routes_by_round: Dict[int, List[Route]] = defaultdict(list)
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
        """Check if layover occurs during late night (e.g. 00:00 - 05:00)"""
        # Simplified check
        return arrival.hour < 5 or departure.hour < 5

    def _is_safe_station(self, station_id: int) -> bool:
        """Check if station is considered safe based on safety_score."""
        session = SessionLocal()
        try:
            stop = session.query(Stop).filter(Stop.id == station_id).first()
            if stop and getattr(stop, 'safety_score', 50.0) < 40.0: # Threshold for 'unsafe'
                return False
            return True
        finally:
            session.close()

    async def _deduplicate_routes(self, routes: List[Route], graph: Optional[TimeDependentGraph] = None) -> List[Route]:
        """Deduplicate + dominance-prune routes."""
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
        
        # Penalize for each transfer (reliability risk)
        score *= (0.95 ** len(route.transfers))
        
        # Penalize tight transfers
        for t in route.transfers:
            if t.duration_minutes < 30:
                score *= 0.8
            elif t.duration_minutes < 60:
                score *= 0.9
                
        # Penalize long journeys
        if route.total_duration > 720: # 12 hours
            score *= 0.95
            
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

    async def _estimate_route_capacity(self, route: Route, constraints: RouteConstraints) -> float:
        """
        Estimates the probability of being able to book this entire route.
        P(Route) = Product of P(Segment)
        """
        session = SessionLocal()
        try:
            total_prob = 1.0
            travel_date = route.segments[0].departure_time
            
            for segment in route.segments:
                # Use secondary train_number if available, else fallback to trip_id
                train_no = segment.train_number if segment.train_number else str(segment.trip_id)
                
                prob = self.capacity_model.predict_availability_probability(
                    session, 
                    train_no, 
                    constraints.preferred_class or "SL", 
                    travel_date
                )
                total_prob *= prob
                
            return total_prob
        except Exception as e:
            logger.error(f"Error estimating route capacity: {e}")
            return 1.0 # Optimistic fallback
        finally:
            session.close()

    async def _score_with_reliability(self, route: Route, constraints: RouteConstraints) -> float:
        """Calculate weighted score including reliability bias (Phase-6)."""
        # Base scoring
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
        
        # Estimate reliability
        reliability = await self._estimate_route_reliability(route, constraints)
        route.reliability = reliability

        # Phase 8: Estimate Availability (Capacity Prediction)
        availability_prob = await self._estimate_route_capacity(route, constraints)
        route.availability_probability = availability_prob

        # Phase 4: Calculate Transfer Risk and apply to score
        transfer_risk_penalty = 0.0
        if route.transfers and route.segments:
            for i, transfer in enumerate(route.transfers):
                previous_segment_trip_id = route.segments[i].trip_id if i < len(route.segments) else None
                risk = await self.transfer_intelligence_manager.calculate_transfer_risk(
                    transfer, previous_segment_trip_id, route, constraints
                )
                transfer_risk_penalty += risk * 100 # Scale risk to penalty points

        # Apply reliability bias to score: lower is better, so high reliability reduces score
        # bias = (1.0 - weight) + (weight * (1.0 / reliability))
        weight = constraints.reliability_weight if hasattr(constraints, 'reliability_weight') else 0.5
        reliability_penalty = (1.0 / max(0.1, reliability)) * weight * 10.0

        # Phase 8: Apply Capacity Penalty (Load Balancing)
        cap_weight = getattr(constraints, 'capacity_weight', 0.4)
        capacity_penalty = self.capacity_model.get_occupancy_penalty(availability_prob) * cap_weight
        
        return base_score + reliability_penalty + transfer_risk_penalty + capacity_penalty

    # --- Validation Facades ---
    def validate_resilience(self, validation_config: dict = None) -> bool:
        """Run chaos / failure-recovery validations."""
        if validation_config is None:
            validation_config = {}
        report = self.validation_manager.validate(
            validation_config,
            profile=ValidationProfile.FULL,
            specific_categories={ValidationCategory.RESILIENCE}
        )
        return report.all_passed

    def validate_production_excellence(self, validation_config: dict = None) -> bool:
        """Run production-excellence validations."""
        if validation_config is None:
            validation_config = {}
        report = self.validation_manager.validate(
            validation_config,
            profile=ValidationProfile.STANDARD,
            specific_categories={ValidationCategory.PRODUCTION_EXCELLENCE}
        )
        return report.all_passed

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
                            'fare': seg.fare,
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
                    departure_code=seg_data.get('departure_code', ''),
                    arrival_code=seg_data.get('arrival_code', ''),
                    fare=seg_data.get('fare', seg_data.get('fare_amount', 0)),
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


class HybridRAPTOR(OptimizedRAPTOR):
    """Hybrid Hub-RAPTOR Implementation (Phase 3)"""

    def __init__(self, hub_manager: HubManager, max_transfers: int = 3,
                 graph_builder: Optional[GraphBuilder] = None, 
                 snapshot_manager: Optional[SnapshotManager] = None):
        super().__init__(max_transfers, graph_builder=graph_builder, snapshot_manager=snapshot_manager)
        self.hub_manager = hub_manager
        self._hub_table: Optional[HubConnectivityTable] = None # Make it private and optional

    def set_hub_table(self, hub_table: HubConnectivityTable):
        self._hub_table = hub_table

    async def find_routes(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: Optional[TimeDependentGraph] = None) -> List[Route]:
        """Hybrid Search Flow (Step 3)"""
        # RailwayRouteEngine should always provide the graph.
        # If it's None here, it means this find_routes was called directly,
        # so we build it.
        if graph is None:
             graph = await self._get_graph_for_internal_use(departure_date)

        # 1. Standard RAPTOR logic for the whole path (local search)
        standard_routes = await super().find_routes(source_stop_id, dest_stop_id, departure_date, constraints, graph)

        # 2. Hybrid Hub Search logic (Phase 3)
        source_hubs = self.hub_manager.get_nearest_hubs(source_stop_id, graph)
        dest_hubs = self.hub_manager.get_nearest_hubs(dest_stop_id, graph)

        hub_routes = []
        if source_hubs and dest_hubs and self._hub_table: # Check if hub_table is set
            # Step 3.1: Hub Search Flow - Identification (Source -> Hubs)
            for s_hub_id, s_travel_time in source_hubs:
                for d_hub_id, d_travel_time in dest_hubs:
                    # Step 3.2: Hub Search Flow - Fast Backbone (Hub -> Hub)
                    hub_dist = self._hub_table.get_min_time(s_hub_id, d_hub_id) # Use _hub_table
                    
                    if hub_dist is not None:
                        # Construct a skeleton route representing the Hub backbone
                        # In production, we'd fetch the best trip segments here.
                        route = Route()
                        # Add a dummy cost and duration representing the backbone
                        route.total_duration = s_travel_time + hub_dist + d_travel_time
                        route.reliability = 0.95 # Generic backbone reliability
                        hub_routes.append(route)

        # 3. Pareto Merge (Step 4)
        return self._pareto_merge(standard_routes, hub_routes)

    async def _get_graph_for_internal_use(self, date: datetime) -> TimeDependentGraph:
        """
        Internal method for HybridRAPTOR to get a graph if not provided externally.
        This is for cases like HubManager precomputation which needs a graph.
        """
        # Attempt to load from snapshot first
        snapshot = await self.snapshot_manager.load_snapshot(date)
        if snapshot:
            graph = TimeDependentGraph(snapshot=snapshot)
            logger.debug(f"HybridRAPTOR internal: Loaded graph from snapshot for {date.date()}")
        else:
            graph = await self.graph_builder.build_graph(date)
            logger.debug(f"HybridRAPTOR internal: Built graph from database for {date.date()}")
        return graph

    def _pareto_merge(self, routes_a: List[Route], routes_b: List[Route]) -> List[Route]:
        """Merge results and choose best (Step 4: Pareto Merge)"""
        combined = routes_a + routes_b
        
        if not combined:
            return []
            
        # Multi-dimensional dominance pruning
        # (duration, cost, transfers, reliability)
        combined.sort(key=lambda r: (r.total_duration, r.total_cost, len(r.transfers)))
        
        pareto_front = []
        for r in combined:
            is_dominated = False
            for p in pareto_front:
                # p dominates r if p is better or equal in all dimensions and strictly better in one
                if (p.total_duration <= r.total_duration and 
                    p.total_cost <= r.total_cost and 
                    len(p.transfers) <= len(r.transfers) and
                    p.reliability >= r.reliability):
                    
                    if (p.total_duration < r.total_duration or 
                        p.total_cost < r.total_cost or 
                        len(p.transfers) < len(r.transfers) or
                        p.reliability > r.reliability):
                        is_dominated = True
                        break
            
            if not is_dominated:
                # ONLY add routes that actually have segments (Filter Phase 3 Hub skeletons)
                if len(r.segments) > 0:
                    pareto_front.append(r)
                else:
                    logger.debug(f"Discarding empty skeleton route with duration {r.total_duration}")
                    
        return pareto_front[:10]