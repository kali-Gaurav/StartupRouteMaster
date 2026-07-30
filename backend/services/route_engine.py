"""
Route Engine - Multi-transfer route discovery using RAPTOR algorithm.
Implements demand-based redistribution and route optimization.
"""

import logging
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from heapq import heappush, heappop

from database.models import Route, Stop, Schedule, Train

logger = logging.getLogger("route_engine")


# CAT Integration
try:
    from backend.cat.client.cat_client import CATClient, create_cat_client, CATClientError, CATClientTimeoutError
    from backend.cat.models.schemas import AvailabilityPrediction
    CAT_AVAILABLE = True
except ImportError:
    CAT_AVAILABLE = False
    CATClient = Any
    CATClientError = Exception
    CATClientTimeoutError = Exception
    AvailabilityPrediction = Any
    logger.warning("CAT client not available, availability predictions will not be used")


@dataclass(order=True)
class RouteSegment:
    """A single leg of a journey."""
    train_number: str
    train_name: str
    from_station_code: str
    from_station_name: str
    to_station_code: str
    to_station_name: str
    departure_time: time
    arrival_time: time
    duration_minutes: int
    class_type: str
    fare: float
    availability: str = "AVAILABLE"


@dataclass(order=True)
class Journey:
    """Complete journey with one or more segments."""
    journey_id: str
    segments: List[RouteSegment]
    total_duration: int
    total_fare: float
    transfers: int
    departure_time: time
    arrival_time: time
    availability_status: str = "AVAILABLE"
    safety_score: int = 100
    demand_factor: float = 1.0
    
    def __post_init__(self):
        if not self.segments:
            raise ValueError("Journey must have at least one segment")
        self.departure_time = self.segments[0].departure_time
        self.arrival_time = self.segments[-1].arrival_time


class RouteEngine:
    """
    Multi-algorithm route discovery engine.
    
    Implements:
    - TurboRouter for direct routes
    - Hub Intersection for 1-transfer routes
    - RAPTOR for multi-transfer routes
    """
    
    def __init__(self):
        self.cache = {}
        self.demand_cache = {}
        self._cat_client: Optional[CATClient] = None
        self._cat_enabled = CAT_AVAILABLE
        self._cat_fallback_enabled = True
        self._cat_timeout = 2.0  # 2 second timeout for CAT predictions
        self._cat_cache: Dict[str, AvailabilityPrediction] = {}
        self._cat_cache_ttl = 300  # 5 minutes
    
    def _get_cat_client(self) -> Optional[CATClient]:
        """Get or create CAT client."""
        if not self._cat_enabled:
            return None
        
        if self._cat_client is None:
            try:
                self._cat_client = create_cat_client(
                    timeout=self._cat_timeout,
                    enable_caching=True
                )
                logger.info("CAT client initialized for route engine")
            except Exception as e:
                logger.warning(f"Failed to initialize CAT client: {e}")
                self._cat_enabled = False
                return None
        
        return self._cat_client
    
    async def _get_availability_prediction(
        self,
        location_id: str,
        prediction_time: datetime
    ) -> Optional[AvailabilityPrediction]:
        """
        Get availability prediction from CAT service.
        
        Args:
            location_id: Location ID to predict
            prediction_time: Time to predict availability for
            
        Returns:
            AvailabilityPrediction or None if CAT unavailable
        """
        if not self._cat_enabled:
            return None
        
        # Check local cache first
        cache_key = f"{location_id}:{prediction_time.isoformat()}"
        if cache_key in self._cat_cache:
            cached = self._cat_cache[cache_key]
            cached_time = datetime.fromisoformat(cached.prediction_time.replace('Z', '+00:00'))
            if (prediction_time - cached_time).total_seconds() < self._cat_cache_ttl:
                return cached
        
        try:
            client = self._get_cat_client()
            if client is None:
                return None
            
            prediction = await client.predict(
                location_id=location_id,
                prediction_time=prediction_time
            )
            
            # Cache the prediction
            self._cat_cache[cache_key] = prediction
            
            return prediction
            
        except CATClientTimeoutError:
            logger.warning(f"CAT prediction timed out for {location_id}")
            if self._cat_fallback_enabled:
                return None
            raise
        except CATClientError as e:
            logger.warning(f"CAT prediction failed for {location_id}: {e}")
            if self._cat_fallback_enabled:
                return None
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting CAT prediction for {location_id}: {e}")
            if self._cat_fallback_enabled:
                return None
            raise
    
    def _get_availability_prediction_sync(
        self,
        location_id: str,
        prediction_time: datetime
    ) -> Optional[AvailabilityPrediction]:
        """
        Synchronous version of _get_availability_prediction.
        
        Args:
            location_id: Location ID to predict
            prediction_time: Time to predict availability for
            
        Returns:
            AvailabilityPrediction or None if CAT unavailable
        """
        if not self._cat_enabled:
            return None
        
        # Check local cache first
        cache_key = f"{location_id}:{prediction_time.isoformat()}"
        if cache_key in self._cat_cache:
            cached = self._cat_cache[cache_key]
            cached_time = datetime.fromisoformat(cached.prediction_time.replace('Z', '+00:00'))
            if (prediction_time - cached_time).total_seconds() < self._cat_cache_ttl:
                return cached
        
        try:
            client = self._get_cat_client()
            if client is None:
                return None
            
            prediction = client.predict_sync(
                location_id=location_id,
                prediction_time=prediction_time
            )
            
            # Cache the prediction
            self._cat_cache[cache_key] = prediction
            
            return prediction
            
        except CATClientTimeoutError:
            logger.warning(f"CAT prediction timed out for {location_id}")
            if self._cat_fallback_enabled:
                return None
            raise
        except CATClientError as e:
            logger.warning(f"CAT prediction failed for {location_id}: {e}")
            if self._cat_fallback_enabled:
                return None
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting CAT prediction for {location_id}: {e}")
            if self._cat_fallback_enabled:
                return None
            raise
    
    def _apply_availability_to_journey(
        self,
        journey: Journey,
        travel_date: date
    ) -> Journey:
        """
        Apply CAT availability prediction to a journey.
        
        Incorporates availability probability into route scoring
        and adjusts journey properties accordingly.
        
        Args:
            journey: Journey to update
            travel_date: Date of travel
            
        Returns:
            Updated journey with availability information
        """
        if not self._cat_enabled:
            return journey
        
        try:
            # Get prediction time (departure time of first segment)
            departure_time = journey.segments[0].departure_time
            prediction_time = datetime.combine(travel_date, departure_time)
            
            # Get location ID from first segment
            location_id = journey.segments[0].from_station_code
            
            # Get availability prediction
            prediction = self._get_availability_prediction_sync(
                location_id=location_id,
                prediction_time=prediction_time
            )
            
            if prediction is not None:
                # Apply availability probability to journey
                availability_prob = prediction.probability
                
                # Adjust availability status based on prediction
                if availability_prob >= 0.8:
                    journey.availability_status = "AVAILABLE"
                elif availability_prob >= 0.5:
                    journey.availability_status = "LIMITED"
                elif availability_prob >= 0.3:
                    journey.availability_status = "WAITLIST"
                else:
                    journey.availability_status = "UNAVAILABLE"
                
                # Update safety score based on availability
                # Higher availability = higher safety score
                journey.safety_score = int(availability_prob * 100)
                
                logger.debug(
                    f"Applied CAT prediction for {location_id}: "
                    f"prob={availability_prob:.2f}, status={journey.availability_status}"
                )
            
            return journey
            
        except Exception as e:
            logger.warning(f"Failed to apply CAT prediction to journey: {e}")
            return journey
    
    async def search_routes(
        self,
        source_code: str,
        dest_code: str,
        travel_date: date,
        max_transfers: int = 3,
        class_type: Optional[str] = None,
        persona: str = "comfort"
    ) -> List[Journey]:
        """
        Search for routes between source and destination.
        
        Args:
            source_code: Origin station code
            dest_code: Destination station code
            travel_date: Date of travel
            max_transfers: Maximum number of transfers allowed
            class_type: Preferred class type
            persona: User persona (comfort, budget, fast)
            
        Returns:
            List of Journey objects sorted by persona preference
        """
        cache_key = f"{source_code}:{dest_code}:{travel_date}:{max_transfers}:{class_type}"
        
        # Check cache
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if datetime.now() - cached["timestamp"] < timedelta(minutes=5):
                return cached["journeys"]
        
        # Execute multi-tier search
        all_journeys = []
        
        # Tier 1: Direct routes (TurboRouter)
        direct_routes = await self._search_direct_routes(
            source_code, dest_code, travel_date, class_type
        )
        all_journeys.extend(direct_routes)
        
        # Tier 2: 1-transfer routes (Hub Intersection)
        if max_transfers >= 1:
            one_transfer = await self._search_one_transfer_routes(
                source_code, dest_code, travel_date, class_type
            )
            all_journeys.extend(one_transfer)
        
        # Tier 3: Multi-transfer routes (RAPTOR)
        if max_transfers >= 2:
            multi_transfer = await self._raptor_search(
                source_code, dest_code, travel_date, class_type, max_transfers
            )
            all_journeys.extend(multi_transfer)
        
        # Deduplicate and merge
        unique_journeys = self._deduplicate_journeys(all_journeys)
        
        # Apply persona-based ranking
        ranked_journeys = self._rank_by_persona(unique_journeys, persona)
        
        # Apply demand-based redistribution
        ranked_journeys = self._apply_demand_factors(ranked_journeys, travel_date)
        
        # Apply CAT availability predictions to journeys
        ranked_journeys = self._apply_cat_availability(ranked_journeys, travel_date)
        
        # Cache results
        self.cache[cache_key] = {
            "timestamp": datetime.now(),
            "journeys": ranked_journeys
        }
        
        return ranked_journeys
    
    async def _search_direct_routes(
        self,
        source_code: str,
        dest_code: str,
        travel_date: date,
        class_type: Optional[str]
    ) -> List[Journey]:
        """Search for direct routes (TurboRouter algorithm)."""
        journeys = []
        
        # Query database for direct routes
        # In production, this would query the actual database
        # For now, return mock data structure
        
        try:
            from database.session import get_db
            db = next(get_db())
            
            # Find trains that go from source to dest
            routes = db.query(Route).filter(
                Route.source_code == source_code,
                Route.dest_code == dest_code
            ).all()
            
            for route in routes:
                # Get schedule for travel date
                schedules = db.query(Schedule).filter(
                    Schedule.route_id == route.id,
                    Schedule.travel_date == travel_date
                ).all()
                
                for schedule in schedules:
                    journey = self._create_journey_from_schedule(
                        schedule, route, class_type
                    )
                    if journey:
                        journeys.append(journey)
                        
        except Exception as e:
            logger.error(f"Error searching direct routes: {e}")
        
        return journeys
    
    async def _search_one_transfer_routes(
        self,
        source_code: str,
        dest_code: str,
        travel_date: date,
        class_type: Optional[str]
    ) -> List[Journey]:
        """
        Search for routes with exactly one transfer (Hub Intersection).
        
        Algorithm:
        1. Find all trains from source to any hub station
        2. Find all trains from hub stations to destination
        3. Combine valid connections with minimum connection time
        """
        journeys = []
        
        try:
            from database.session import get_db
            db = next(get_db())
            
            # Find hub stations (stations with high connectivity)
            hub_stations = await self._identify_hub_stations(source_code, dest_code)
            
            for hub in hub_stations[:5]:  # Limit to top 5 hubs
                # Get first leg
                first_leg_routes = db.query(Route).filter(
                    Route.source_code == source_code,
                    Route.dest_code == hub
                ).all()
                
                # Get second leg
                second_leg_routes = db.query(Route).filter(
                    Route.source_code == hub,
                    Route.dest_code == dest_code
                ).all()
                
                # Find valid connections
                for first in first_leg_routes:
                    first_schedules = db.query(Schedule).filter(
                        Schedule.route_id == first.id,
                        Schedule.travel_date == travel_date
                    ).all()
                    
                    for second in second_leg_routes:
                        second_schedules = db.query(Schedule).filter(
                            Schedule.route_id == second.id,
                            Schedule.travel_date == travel_date
                        ).all()
                        
                        # Check connection times
                        for fs in first_schedules:
                            for ss in second_schedules:
                                if self._is_valid_connection(fs, ss, hub):
                                    journey = self._create_transfer_journey(
                                        fs, ss, first, second, class_type
                                    )
                                    if journey:
                                        journeys.append(journey)
                        
        except Exception as e:
            logger.error(f"Error searching one-transfer routes: {e}")
        
        return journeys
    
    async def _raptor_search(
        self,
        source_code: str,
        dest_code: str,
        travel_date: date,
        class_type: Optional[str],
        max_transfers: int
    ) -> List[Journey]:
        """
        RAPTOR (Real-time Algorithm for Public Transport Optimization and Routing).
        
        Finds optimal routes with multiple transfers using label-setting algorithm.
        """
        journeys = []
        
        try:
            from database.session import get_db
            db = next(get_db())
            
            # Get all stops and their connections
            stops = await self._get_stop_connections(source_code, dest_code, travel_date)
            
            if not stops:
                return journeys
            
            # RAPTOR algorithm
            # Initialize labels
            labels = {source_code: [0, None, None]}  # [arrival_time, journey, previous_stop]
            queue = [(0, source_code)]  # (arrival_time, stop)
            
            iterations = 0
            max_iterations = max_transfers + 1
            
            while queue and iterations < max_iterations:
                iterations += 1
                
                new_labels = {}
                new_queue = []
                
                while queue:
                    _, current_stop = heappop(queue)
                    
                    # Get all trips departing from current stop
                    trips = await self._get_departing_trips(
                        current_stop, travel_date, class_type
                    )
                    
                    for trip in trips:
                        arrival_time = self._time_to_minutes(trip.arrival_time)
                        
                        # Check if this improves destination arrival
                        if trip.to_station not in labels or arrival_time < labels[trip.to_station][0]:
                            labels[trip.to_station] = [arrival_time, trip, current_stop]
                            
                            if trip.to_station not in new_queue:
                                heappush(new_queue, (arrival_time, trip.to_station))
                
                queue = new_queue
            
            # Reconstruct journey to destination
            if dest_code in labels:
                journey = self._reconstruct_journey(labels, source_code, dest_code)
                if journey:
                    journeys.append(journey)
                    
        except Exception as e:
            logger.error(f"Error in RAPTOR search: {e}")
        
        return journeys
    
    async def _identify_hub_stations(
        self,
        source_code: str,
        dest_code: str,
        travel_date: date = None
    ) -> List[str]:
        """
        Identify optimal transfer hubs based on:
        1. Route connectivity (number of connections)
        2. Geographic position (between source and dest)
        3. Historical transfer success rate
        4. Available capacity at hub
        """
        try:
            from database.session import get_db
            db = next(get_db())
            
            # Get all stations with routes from source
            source_connections = db.query(Route.dest_code).filter(
                Route.source_code == source_code
            ).distinct().all()
            
            # Get all stations with routes to destination
            dest_connections = db.query(Route.source_code).filter(
                Route.dest_code == dest_code
            ).distinct().all()
            
            # Find intersection (potential hubs)
            source_set = {c[0] for c in source_connections}
            dest_set = {c[0] for c in dest_connections}
            potential_hubs = source_set & dest_set
            
            # Remove source and destination from hubs
            potential_hubs = potential_hubs - {source_code, dest_code}
            
            # Score hubs based on:
            # 1. Number of connections from source
            # 2. Number of connections to destination
            hub_scores = []
            
            for hub in potential_hubs:
                score = 0
                
                # Connection count score
                source_count = db.query(Route).filter(
                    Route.source_code == source_code,
                    Route.dest_code == hub
                ).count()
                
                dest_count = db.query(Route).filter(
                    Route.source_code == hub,
                    Route.dest_code == dest_code
                ).count()
                
                score += source_count * 10 + dest_count * 10
                
                # Add some hubs with high connectivity even if not in intersection
                hub_scores.append((hub, score))
            
            # Sort by score and return top 10
            hub_scores.sort(key=lambda x: x[1], reverse=True)
            top_hubs = [h[0] for h in hub_scores[:10]]
            
            # If no good hubs found, use fallback
            if not top_hubs:
                logger.warning(f"No optimal hubs found for {source_code} -> {dest_code}, using fallback")
                return self._get_fallback_hubs()
            
            return top_hubs
            
        except Exception as e:
            logger.error(f"Error identifying hub stations: {e}")
            # Fallback to common hubs
            return self._get_fallback_hubs()
    
    def _get_fallback_hubs(self) -> List[str]:
        """Get fallback hub stations for common routes."""
        return ["NDLS", "BCT", "MAS", "HWH", "SC", "LKO", "JP", "DHN", "GKP", "PNBE"]
    
    async def _get_stop_connections(
        self,
        source_code: str,
        dest_code: str,
        travel_date: date
    ) -> Dict[str, List]:
        """Get all stops and their connections."""
        connections = defaultdict(list)
        
        try:
            from database.session import get_db
            db = next(get_db())
            
            routes = db.query(Route).filter(
                or_(
                    Route.source_code == source_code,
                    Route.dest_code == dest_code
                )
            ).all()
            
            for route in routes:
                connections[route.source_code].append({
                    "to": route.dest_code,
                    "route_id": route.id
                })
                
        except Exception as e:
            logger.error(f"Error getting stop connections: {e}")
        
        return connections
    
    async def _get_departing_trips(
        self,
        from_station: str,
        travel_date: date,
        class_type: Optional[str]
    ) -> List[RouteSegment]:
        """Get all departing trips from a station."""
        trips = []
        
        try:
            from database.session import get_db
            db = next(get_db())
            
            routes = db.query(Route).filter(
                Route.source_code == from_station
            ).limit(50).all()
            
            for route in routes:
                schedules = db.query(Schedule).filter(
                    Schedule.route_id == route.id,
                    Schedule.travel_date == travel_date
                ).first()
                
                if schedules:
                    segment = self._create_segment_from_route(route, schedules, class_type)
                    if segment:
                        trips.append(segment)
                        
        except Exception as e:
            logger.error(f"Error getting departing trips: {e}")
        
        return trips
    
    def _is_valid_connection(
        self,
        first_schedule: Schedule,
        second_schedule: Schedule,
        hub_station: str,
        min_connection_minutes: int = 30
    ) -> bool:
        """Check if connection between two schedules is valid."""
        first_arrival = self._time_to_minutes(first_schedule.arrival_time)
        second_departure = self._time_to_minutes(second_schedule.departure_time)
        
        # Allow overnight connections
        if second_departure < first_arrival:
            second_departure += 24 * 60
        
        return (second_departure - first_arrival) >= min_connection_minutes
    
    def _create_journey_from_schedule(
        self,
        schedule: Schedule,
        route: Route,
        class_type: Optional[str]
    ) -> Optional[Journey]:
        """Create a Journey object from schedule and route."""
        try:
            segment = RouteSegment(
                train_number=schedule.train_number,
                train_name=route.train_name,
                from_station_code=route.source_code,
                from_station_name=route.source_name,
                to_station_code=route.dest_code,
                to_station_name=route.dest_name,
                departure_time=schedule.departure_time,
                arrival_time=schedule.arrival_time,
                duration_minutes=schedule.duration_minutes,
                class_type=class_type or "SL",
                fare=schedule.base_fare,
                availability=schedule.availability_status
            )
            
            return Journey(
                journey_id=f"{schedule.train_number}:{route.source_code}:{route.dest_code}",
                segments=[segment],
                total_duration=schedule.duration_minutes,
                total_fare=schedule.base_fare,
                transfers=0,
                departure_time=schedule.departure_time,
                arrival_time=schedule.arrival_time,
                availability_status=schedule.availability_status
            )
        except Exception as e:
            logger.error(f"Error creating journey: {e}")
            return None
    
    def _create_transfer_journey(
        self,
        first_schedule: Schedule,
        second_schedule: Schedule,
        first_route: Route,
        second_route: Route,
        class_type: Optional[str]
    ) -> Optional[Journey]:
        """Create a journey with one transfer."""
        try:
            first_segment = RouteSegment(
                train_number=first_schedule.train_number,
                train_name=first_route.train_name,
                from_station_code=first_route.source_code,
                from_station_name=first_route.source_name,
                to_station_code=first_route.dest_code,
                to_station_name=first_route.dest_name,
                departure_time=first_schedule.departure_time,
                arrival_time=first_schedule.arrival_time,
                duration_minutes=first_schedule.duration_minutes,
                class_type=class_type or "SL",
                fare=first_schedule.base_fare,
                availability=first_schedule.availability_status
            )
            
            second_segment = RouteSegment(
                train_number=second_schedule.train_number,
                train_name=second_route.train_name,
                from_station_code=second_route.source_code,
                from_station_name=second_route.source_name,
                to_station_code=second_route.dest_code,
                to_station_name=second_route.dest_name,
                departure_time=second_schedule.departure_time,
                arrival_time=second_schedule.arrival_time,
                duration_minutes=second_schedule.duration_minutes,
                class_type=class_type or "SL",
                fare=second_schedule.base_fare,
                availability=second_schedule.availability_status
            )
            
            # Calculate total duration including connection time
            first_arrival = self._time_to_minutes(first_schedule.arrival_time)
            second_departure = self._time_to_minutes(second_schedule.departure_time)
            if second_departure < first_arrival:
                second_departure += 24 * 60
            connection_time = second_departure - first_arrival
            total_duration = first_schedule.duration_minutes + connection_time + second_schedule.duration_minutes
            
            total_fare = first_schedule.base_fare + second_schedule.base_fare
            
            # Determine availability
            availability = "AVAILABLE"
            if first_segment.availability != "AVAILABLE" or second_segment.availability != "AVAILABLE":
                availability = "WAITLIST"
            
            return Journey(
                journey_id=f"{first_schedule.train_number}+{second_schedule.train_number}",
                segments=[first_segment, second_segment],
                total_duration=total_duration,
                total_fare=total_fare,
                transfers=1,
                departure_time=first_schedule.departure_time,
                arrival_time=second_schedule.arrival_time,
                availability_status=availability
            )
        except Exception as e:
            logger.error(f"Error creating transfer journey: {e}")
            return None
    
    def _reconstruct_journey(
        self,
        labels: Dict[str, List],
        source_code: str,
        dest_code: str
    ) -> Optional[Journey]:
        """Reconstruct journey from RAPTOR labels."""
        try:
            segments = []
            current = dest_code
            
            while current != source_code:
                label = labels[current]
                trip = label[1]
                if trip is None:
                    return None
                segments.append(trip)
                current = label[2]
            
            segments.reverse()
            
            if not segments:
                return None
            
            total_duration = sum(s.duration_minutes for s in segments)
            total_fare = sum(s.fare for s in segments)
            
            return Journey(
                journey_id="raptor:" + "-".join(s.train_number for s in segments),
                segments=segments,
                total_duration=total_duration,
                total_fare=total_fare,
                transfers=len(segments) - 1,
                departure_time=segments[0].departure_time,
                arrival_time=segments[-1].arrival_time
            )
        except Exception as e:
            logger.error(f"Error reconstructing journey: {e}")
            return None
    
    def _deduplicate_journeys(self, journeys: List[Journey]) -> List[Journey]:
        """Remove duplicate journeys."""
        seen = set()
        unique = []
        
        for journey in journeys:
            # Create signature from train numbers
            signature = tuple(s.train_number for s in journey.segments)
            if signature not in seen:
                seen.add(signature)
                unique.append(journey)
        
        return unique
    
    def _rank_by_persona(
        self,
        journeys: List[Journey],
        persona: str
    ) -> List[Journey]:
        """Rank journeys based on user persona."""
        if persona == "comfort":
            # Prioritize fewer transfers, higher availability
            return sorted(journeys, key=lambda j: (
                j.transfers,
                -j.safety_score,
                j.total_fare
            ))
        elif persona == "budget":
            # Prioritize lower fare
            return sorted(journeys, key=lambda j: (
                j.total_fare,
                j.transfers
            ))
        elif persona == "fast":
            # Prioritize shorter duration
            return sorted(journeys, key=lambda j: (
                j.total_duration,
                j.transfers
            ))
        else:
            # Default: balanced ranking
            return sorted(journeys, key=lambda j: (
                j.transfers * 10 + j.total_duration / 60 + j.total_fare / 100
            ))
    
    def _apply_cat_availability(
        self,
        journeys: List[Journey],
        travel_date: date
    ) -> List[Journey]:
        """
        Apply CAT availability predictions to all journeys.
        
        Args:
            journeys: List of journeys to update
            travel_date: Date of travel
            
        Returns:
            Updated list of journeys with availability information
        """
        if not self._cat_enabled:
            return journeys
        
        updated_journeys = []
        
        for journey in journeys:
            updated_journey = self._apply_availability_to_journey(journey, travel_date)
            updated_journeys.append(updated_journey)
        
        return updated_journeys
    
    def _apply_demand_factors(
        self,
        journeys: List[Journey],
        travel_date: date,
        source_code: str = None,
        dest_code: str = None
    ) -> List[Journey]:
        """
        Apply demand-based pricing and redistribution.
        
        Tries ML-based demand prediction first, falls back to basic factors.
        """
        try:
            # Try to use ML demand prediction
            from services.demand_forecaster import demand_forecaster
            
            if source_code and dest_code:
                # Get demand forecast for the corridor
                demand_forecast = demand_forecaster.get_corridor_demand(
                    source_code=source_code,
                    dest_code=dest_code,
                    travel_date=travel_date
                )
                
                # Get surge probability
                surge_prob = demand_forecaster.get_surge_probability(
                    source_code=source_code,
                    dest_code=dest_code,
                    travel_date=travel_date
                )
                
                for journey in journeys:
                    # Base demand factor from ML model
                    base_factor = demand_forecast.demand_factor
                    
                    # Surge adjustment
                    surge_adjustment = 1.0 + (surge_prob * 0.3)  # Up to 30% surge
                    
                    # Capacity utilization adjustment
                    if demand_forecast.capacity_utilization > 0.9:
                        surge_adjustment *= 1.1  # 10% extra for high utilization
                    
                    # Apply to journey
                    journey.demand_factor = base_factor * surge_adjustment
                    journey.total_fare = journey.total_fare * journey.demand_factor
                    
                    # Update availability status based on demand
                    if demand_forecast.demand_level in ["SURGE", "OVERFLOW"]:
                        journey.availability_status = "LIMITED"
                
                return journeys
            
        except Exception as e:
            logger.warning(f"ML demand prediction unavailable, using basic factors: {e}")
        
        # Fallback to basic demand factors
        demand_factor = self._calculate_demand_factor(travel_date)
        
        for journey in journeys:
            journey.demand_factor = demand_factor
            journey.total_fare = journey.total_fare * demand_factor
        
        return journeys
    
    def _calculate_demand_factor(self, travel_date: date) -> float:
        """Calculate demand factor for a date (surge pricing)."""
        # High demand periods
        now = datetime.now().date()
        days_ahead = (travel_date - now).days
        
        if days_ahead < 0:
            return 1.0  # Past dates
        
        # Weekend premium
        if travel_date.weekday() >= 5:  # Saturday or Sunday
            return 1.2
        
        # Festival/holiday premium (simplified)
        holiday_dates = [
            date(2025, 1, 1),   # New Year
            date(2025, 1, 14),  # Makar Sankranti
            date(2025, 1, 26),  # Republic Day
            date(2025, 8, 15),  # Independence Day
            date(2025, 10, 2),  # Gandhi Jayanti
            date(2025, 10, 31), # Diwali
            date(2025, 12, 25), # Christmas
        ]
        
        if travel_date in holiday_dates:
            return 1.5
        
        # Last minute premium (within 3 days)
        if days_ahead <= 3:
            return 1.3
        
        # Advance booking discount
        if days_ahead > 30:
            return 0.95
        
        return 1.0
    
    def _time_to_minutes(self, t: time) -> int:
        """Convert time to minutes since midnight."""
        return t.hour * 60 + t.minute
    
    def _calculate_route_quality_score(self, journey: Journey) -> float:
        """
        Calculate quality score for a route (0-100).
        
        Factors:
        - Safety score (weight: 30%)
        - Availability (weight: 25%)
        - Comfort (weight: 20%)
        - Price value (weight: 15%)
        - Time convenience (weight: 10%)
        """
        # Safety score (already 0-100)
        safety_score = journey.safety_score
        
        # Availability score
        if journey.availability_status == "AVAILABLE":
            availability_score = 100
        elif journey.availability_status == "LIMITED":
            availability_score = 70
        elif journey.availability_status == "WAITLIST":
            availability_score = 40
        else:
            availability_score = 10
        
        # Comfort score (fewer transfers = higher comfort)
        comfort_score = max(0, 100 - (journey.transfers * 25))
        
        # Price value (normalized, lower is better)
        avg_fare = journey.total_fare / max(1, len(journey.segments))
        price_score = max(0, 100 - (avg_fare / 50))  # ₹5000 = 0, ₹0 = 100
        
        # Time convenience (departure time preference)
        departure_minutes = journey.departure_time.hour * 60 + journey.departure_time.minute
        # Prefer departures between 6 AM and 10 PM
        if 6 * 60 <= departure_minutes <= 22 * 60:
            time_score = 100
        else:
            time_score = 50  # Night trains are less convenient
        
        # Weighted average
        quality_score = (
            safety_score * 0.30 +
            availability_score * 0.25 +
            comfort_score * 0.20 +
            price_score * 0.15 +
            time_score * 0.10
        )
        
        return quality_score
    
    def _get_min_connection_time(
        self,
        hub_station: str,
        first_arrival: time,
        second_departure: time
    ) -> int:
        """
        Calculate minimum connection time at a station.
        
        Factors:
        - Station size (larger stations need more time)
        - Time of day (rush hour needs more time)
        - Day of week (weekends may have different patterns)
        """
        # Base connection times by station category
        station_connection_times = {
            "NDLS": 45,  # Large junction
            "BCT": 40,
            "MAS": 45,
            "HWH": 40,
            "SC": 35,
            "LKO": 35,
            "JP": 30,
            "DHN": 30,
            "GKP": 35,
            "PNBE": 35,
        }
        
        base_time = station_connection_times.get(hub_station, 30)
        
        # Adjust for time of day
        arrival_minutes = first_arrival.hour * 60 + first_arrival.minute
        departure_minutes = second_departure.hour * 60 + second_departure.minute
        
        # Rush hour adjustment (7-9 AM, 5-8 PM)
        if (7 * 60 <= arrival_minutes <= 9 * 60) or (17 * 60 <= arrival_minutes <= 20 * 60):
            base_time += 15
        
        # Night adjustment (less staff at night)
        if arrival_minutes < 6 * 60 or arrival_minutes > 23 * 60:
            base_time += 15
        
        return base_time
    
    def _create_segment_from_route(
        self,
        route: Route,
        schedule: Schedule,
        class_type: Optional[str]
    ) -> Optional[RouteSegment]:
        """Create a RouteSegment from route and schedule."""
        try:
            return RouteSegment(
                train_number=schedule.train_number,
                train_name=route.train_name,
                from_station_code=route.source_code,
                from_station_name=route.source_name,
                to_station_code=route.dest_code,
                to_station_name=route.dest_name,
                departure_time=schedule.departure_time,
                arrival_time=schedule.arrival_time,
                duration_minutes=schedule.duration_minutes,
                class_type=class_type or "SL",
                fare=schedule.base_fare,
                availability=schedule.availability_status
            )
        except Exception as e:
            logger.error(f"Error creating segment: {e}")
            return None


# Singleton instance
route_engine = RouteEngine()


def get_route_engine() -> RouteEngine:
    """Get route engine instance."""
    return route_engine