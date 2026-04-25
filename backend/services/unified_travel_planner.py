"""
Unified Travel Planning Service
================================

This is the main orchestration layer that integrates:
1. Crowd Control Service
2. Multi-Modal Planning Service
3. Station Amenity Service
4. Knowledge Graph Service
5. Demand Redistribution Service
6. Pricing Service
7. Search Service
8. Booking Service

This service provides a complete travel planning experience with:
- Smart travel plans with multiple options
- Crowd-aware routing
- Multi-modal journey planning
- Station waiting options
- Redistribution offers

Author: Algorithm Team
Version: 1.0.0
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TravelPreference(Enum):
    """User travel preferences"""
    FASTEST = "fastest"           # Minimize travel time
    CHEAPEST = "cheapest"         # Minimize cost
    COMFORTABLE = "comfortable"   # Maximize comfort
    CROWD_FREE = "crowd_free"     # Avoid crowds
    BALANCED = "balanced"         # Balance all factors


class WaitPreference(Enum):
    """Wait tolerance preferences"""
    NO_WAIT = 0           # Must travel immediately
    SHORT_WAIT = 60       # Up to 1 hour
    MEDIUM_WAIT = 180     # Up to 3 hours
    LONG_WAIT = 360       # Up to 6 hours
    ANY_WAIT = 9999       # Any wait acceptable


@dataclass
class TravelRequest:
    """Complete travel request"""
    # Required
    origin: str
    destination: str
    travel_date: date
    passenger_count: int = 1
    
    # Optional preferences
    travel_preference: TravelPreference = TravelPreference.BALANCED
    wait_preference: WaitPreference = WaitPreference.ANY_WAIT
    max_wait_hours: int = 6
    max_cost: float = 10000
    preferred_class: str = "SL"
    
    # Advanced options
    allow_multi_modal: bool = True
    avoid_high_crowd: bool = True
    requires_accessibility: bool = False
    
    # User context
    user_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class TravelOption:
    """Single travel option in the plan"""
    option_id: str
    option_type: str  # direct, wait, alternative, multi_modal
    
    # Route info
    from_station: str
    to_station: str
    departure_time: datetime
    arrival_time: datetime
    total_duration_minutes: int
    
    # Cost (required - must come before optional fields)
    total_fare: float
    comfort_score: float  # 0-1
    crowd_level: str  # low, moderate, high, critical, full
    crowd_avoidance_score: float  # 0-1
    
    # Wait info (if any) - optional fields
    wait_duration_minutes: int = 0
    wait_station: Optional[str] = None
    wait_amenities: Dict[str, Any] = field(default_factory=dict)
    
    # Segments (for multi-modal)
    segments: List[Dict] = field(default_factory=list)
    
    # Fare breakdown
    fare_breakdown: Dict[str, float] = field(default_factory=dict)
    
    # Train details
    train_numbers: List[str] = field(default_factory=list)
    seat_class: str = "SL"
    seat_available: bool = True
    
    # Recommendation
    is_recommended: bool = False
    recommendation_reason: str = ""
    
    # Alternatives
    alternatives_available: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'option_id': self.option_id,
            'option_type': self.option_type,
            'from': self.from_station,
            'to': self.to_station,
            'departure': self.departure_time.isoformat() if self.departure_time else None,
            'arrival': self.arrival_time.isoformat() if self.arrival_time else None,
            'duration_minutes': self.total_duration_minutes,
            'wait_minutes': self.wait_duration_minutes,
            'wait_station': self.wait_station,
            'total_fare': self.total_fare,
            'fare_breakdown': self.fare_breakdown,
            'comfort_score': round(self.comfort_score, 2),
            'crowd_level': self.crowd_level,
            'crowd_avoidance_score': round(self.crowd_avoidance_score, 2),
            'train_numbers': self.train_numbers,
            'seat_class': self.seat_class,
            'seat_available': self.seat_available,
            'is_recommended': self.is_recommended,
            'recommendation_reason': self.recommendation_reason,
            'segments': self.segments
        }


@dataclass
class TravelPlan:
    """Complete travel plan with multiple options"""
    plan_id: str
    request: TravelRequest
    
    # Options
    options: List[TravelOption] = field(default_factory=list)
    
    # Best options by category
    fastest_option: Optional[TravelOption] = None
    cheapest_option: Optional[TravelOption] = None
    most_comfortable: Optional[TravelOption] = None
    crowd_free_option: Optional[TravelOption] = None
    
    # Station info
    origin_station_info: Dict = field(default_factory=dict)
    destination_station_info: Dict = field(default_factory=dict)
    
    # Metadata
    generated_at: datetime = field(default_factory=datetime.utcnow)
    valid_until: datetime = None
    search_id: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'plan_id': self.plan_id,
            'origin': self.request.origin,
            'destination': self.request.destination,
            'travel_date': self.request.travel_date.isoformat(),
            'passenger_count': self.request.passenger_count,
            'options': [o.to_dict() for o in self.options],
            'recommended': self.get_recommended().to_dict() if self.get_recommended() else None,
            'fastest': self.fastest_option.to_dict() if self.fastest_option else None,
            'cheapest': self.cheapest_option.to_dict() if self.cheapest_option else None,
            'most_comfortable': self.most_comfortable.to_dict() if self.most_comfortable else None,
            'generated_at': self.generated_at.isoformat(),
            'valid_until': self.valid_until.isoformat() if self.valid_until else None
        }
    
    def get_recommended(self) -> Optional[TravelOption]:
        """Get the recommended option"""
        recommended = [o for o in self.options if o.is_recommended]
        return recommended[0] if recommended else (self.options[0] if self.options else None)


class UnifiedTravelPlanner:
    """
    Main orchestration service for travel planning.
    
    This service integrates all the algorithm services to provide
    a complete travel planning experience.
    """
    
    def __init__(self, db=None):
        self.db = db
        self._services = {}
    
    def _get_service(self, service_name: str):
        """Lazy load services"""
        if service_name not in self._services:
            if service_name == "crowd":
                from services.crowd_control_service import get_crowd_control_service
                self._services[service_name] = get_crowd_control_service(self.db)
            elif service_name == "multimodal":
                from services.multimodal_planning_service import get_multimodal_planning_service
                self._services[service_name] = get_multimodal_planning_service(self.db)
            elif service_name == "amenity":
                from services.station_amenity_service import get_station_amenity_service
                self._services[service_name] = get_station_amenity_service(self.db)
            elif service_name == "knowledge":
                from services.knowledge_graph_service import get_knowledge_graph
                self._services[service_name] = get_knowledge_graph()
            elif service_name == "redistribution":
                from services.demand_redistribution_service import get_redistribution_service
                self._services[service_name] = get_redistribution_service(self.db)
            elif service_name == "pricing":
                from services.booking_price_calculator import get_booking_price_calculator
                self._services[service_name] = get_booking_price_calculator(self.db)
            elif service_name == "search":
                from services.search_service import SearchService
                self._services[service_name] = SearchService(db=self.db)
        
        return self._services.get(service_name)
    
    async def create_travel_plan(self, request: TravelRequest) -> TravelPlan:
        """
        Create a complete travel plan with multiple options.
        
        This is the main entry point for travel planning.
        """
        logger.info(f"Creating travel plan: {request.origin} -> {request.destination}")
        
        # Generate plan ID
        plan_id = f"plan_{request.origin}_{request.destination}_{datetime.utcnow().timestamp()}"
        
        # Get station information
        origin_info = await self._get_station_info(request.origin)
        dest_info = await self._get_station_info(request.destination)
        
        # Get crowd data for origin
        crowd_service = self._get_service("crowd")
        origin_crowd = await crowd_service.get_station_crowd(request.origin)
        
        # Search for routes
        routes = await self._search_routes(request)
        
        # Generate options from routes
        options = []
        for i, route in enumerate(routes[:10]):  # Top 10 routes
            option = await self._create_travel_option(
                route, origin_crowd, request, i
            )
            if option:
                options.append(option)
        
        # Add wait options if allowed
        if request.wait_preference != WaitPreference.NO_WAIT and request.max_wait_hours > 0:
            wait_options = await self._create_wait_options(
                options, origin_crowd, request
            )
            options.extend(wait_options)
        
        # Add multi-modal options if allowed
        if request.allow_multi_modal:
            multimodal_options = await self._create_multimodal_options(request)
            options.extend(multimodal_options)
        
        # Filter options based on constraints
        options = self._filter_options(options, request)
        
        # Rank options
        options = self._rank_options(options, request)
        
        # Mark recommended option
        if options:
            options[0].is_recommended = True
            options[0].recommendation_reason = self._get_recommendation_reason(
                options[0], request
            )
        
        # Find best in each category
        fastest = min(options, key=lambda x: x.total_duration_minutes) if options else None
        cheapest = min(options, key=lambda x: x.total_fare) if options else None
        most_comfortable = max(options, key=lambda x: x.comfort_score) if options else None
        crowd_free = max(options, key=lambda x: x.crowd_avoidance_score) if options else None
        
        # Create plan
        plan = TravelPlan(
            plan_id=plan_id,
            request=request,
            options=options,
            fastest_option=fastest,
            cheapest_option=cheapest,
            most_comfortable=most_comfortable,
            crowd_free_option=crowd_free,
            origin_station_info=origin_info,
            destination_station_info=dest_info,
            valid_until=datetime.utcnow() + timedelta(minutes=15)
        )
        
        # Record search for analytics
        await self._record_search(request, plan)
        
        logger.info(f"Travel plan created with {len(options)} options")
        return plan
    
    async def _get_station_info(self, station_code: str) -> Dict:
        """Get station information"""
        try:
            from services.station_service import StationService
            station_service = StationService(self.db)
            station = await station_service.get_station(station_code)
            return station if station else {'code': station_code, 'name': station_code}
        except Exception as e:
            logger.debug(f"Failed to get station info: {e}")
            return {'code': station_code, 'name': station_code}
    
    async def _search_routes(self, request: TravelRequest) -> List[Dict]:
        """Search for available routes"""
        try:
            search_service = self._get_service("search")
            result = await search_service.search_routes(
                source=request.origin,
                destination=request.destination,
                travel_date=request.travel_date.isoformat(),
                quota="GN"
            )
            
            journeys = result.get('data', {}).get('journeys', [])
            return journeys
            
        except Exception as e:
            logger.error(f"Route search failed: {e}")
            return []
    
    async def _create_travel_option(
        self,
        route: Dict,
        origin_crowd,
        request: TravelRequest,
        index: int
    ) -> Optional[TravelOption]:
        """Create a travel option from a route"""
        try:
            # Get train info
            train_number = route.get('train_number', f'TRAIN_{index}')
            train_numbers = [train_number]
            
            # Get crowd data for train
            crowd_service = self._get_service("crowd")
            train_crowd = await crowd_service.get_train_crowd(
                train_number, request.travel_date
            )
            
            # Calculate wait time based on crowd
            wait_duration = self._calculate_wait_time(
                origin_crowd.current_crowd_level.value if origin_crowd else 'moderate',
                train_crowd.crowd_level.value if train_crowd else 'moderate',
                request.wait_preference
            )
            
            # Check if wait exceeds preference
            max_wait = request.max_wait_hours * 60
            if wait_duration > max_wait:
                wait_duration = 0  # Don't offer wait option
            
            # Calculate fare
            base_fare = route.get('fare', 500)
            total_fare = base_fare * request.passenger_count
            
            # Add platform fee
            pricing_service = self._get_service("pricing")
            if pricing_service:
                try:
                    price_calc = await pricing_service.calculate_booking_price(
                        source=request.origin,
                        destination=request.destination,
                        travel_date=request.travel_date,
                        passenger_count=request.passenger_count,
                        train_class=request.preferred_class
                    )
                    if price_calc:
                        total_fare = price_calc.total
                except:
                    pass
            
            # Calculate comfort score
            comfort = self._calculate_comfort(
                train_crowd.crowd_level.value if train_crowd else 'moderate',
                origin_crowd.amenities_score if origin_crowd else 0.5,
                wait_duration
            )
            
            # Calculate crowd avoidance score
            crowd_avoidance = 1.0 - (train_crowd.occupancy_rate if train_crowd else 0.5)
            
            # Determine option type
            option_type = "direct"
            if wait_duration > 0:
                option_type = "wait"
            
            return TravelOption(
                option_id=f"opt_{index}_{datetime.utcnow().timestamp()}",
                option_type=option_type,
                from_station=request.origin,
                to_station=request.destination,
                departure_time=route.get('departure', datetime.utcnow()),
                arrival_time=route.get('arrival', datetime.utcnow()),
                total_duration_minutes=route.get('duration', 0),
                wait_duration_minutes=wait_duration,
                total_fare=total_fare,
                fare_breakdown={
                    'base': base_fare,
                    'passengers': request.passenger_count,
                    'platform_fee': total_fare - (base_fare * request.passenger_count)
                },
                comfort_score=comfort,
                crowd_level=train_crowd.crowd_level.value if train_crowd else 'moderate',
                crowd_avoidance_score=crowd_avoidance,
                train_numbers=train_numbers,
                seat_class=request.preferred_class,
                seat_available=route.get('availability', 0) > 0
            )
            
        except Exception as e:
            logger.error(f"Failed to create travel option: {e}")
            return None
    
    def _calculate_wait_time(
        self,
        station_crowd: str,
        train_crowd: str,
        preference: WaitPreference
    ) -> int:
        """Calculate recommended wait time"""
        crowd_levels = {'low': 0, 'moderate': 1, 'high': 2, 'critical': 3, 'full': 4}
        
        station_level = crowd_levels.get(station_crowd, 1)
        train_level = crowd_levels.get(train_crowd, 1)
        
        # Base wait from station crowd
        base_wait = [0, 15, 30, 60, 120][station_level]
        
        # Add for crowded train
        if train_level >= 3:
            base_wait += 30
        
        # Cap by preference
        return min(base_wait, preference.value)
    
    def _calculate_comfort(
        self,
        train_crowd: str,
        station_amenities: float,
        wait_time: int
    ) -> float:
        """Calculate comfort score"""
        crowd_scores = {
            'low': 1.0,
            'moderate': 0.8,
            'high': 0.6,
            'critical': 0.4,
            'full': 0.2
        }
        
        crowd_score = crowd_scores.get(train_crowd, 0.5)
        amenity_factor = station_amenities * 0.2
        
        # Some wait at good station is better than crowded train
        wait_factor = 0.0
        if wait_time > 0 and station_amenities > 0.7:
            wait_factor = 0.1
        
        return min(1.0, crowd_score + amenity_factor + wait_factor)
    
    async def _create_wait_options(
        self,
        direct_options: List[TravelOption],
        origin_crowd,
        request: TravelRequest
    ) -> List[TravelOption]:
        """Create wait-based options"""
        wait_options = []
        
        # Get station amenities
        amenity_service = self._get_service("amenity")
        try:
            packages = await amenity_service.get_available_packages(
                request.origin,
                request.passenger_count,
                duration_hours=2
            )
        except:
            packages = []
        
        # Create wait option for each direct option
        for i, direct in enumerate(direct_options[:3]):
            if direct.wait_duration_minutes > 0:
                continue  # Already has wait
            
            # Calculate wait time
            wait_time = 60  # 1 hour wait
            
            # Get wait station amenities
            wait_amenities = {}
            if amenity_service and packages:
                wait_amenities = {
                    'packages_available': len(packages),
                    'basic_price': packages[0].base_price if packages else 50,
                    'has_lounge': True,
                    'has_food': True,
                    'has_wifi': True,
                    'language_learning': True  # Free!
                }
            
            # Create wait option
            wait_option = TravelOption(
                option_id=f"wait_opt_{i}_{datetime.utcnow().timestamp()}",
                option_type="wait",
                from_station=direct.from_station,
                to_station=direct.to_station,
                departure_time=direct.departure_time + timedelta(minutes=wait_time),
                arrival_time=direct.arrival_time + timedelta(minutes=wait_time),
                total_duration_minutes=direct.total_duration_minutes + wait_time,
                wait_duration_minutes=wait_time,
                wait_station=request.origin,
                wait_amenities=wait_amenities,
                total_fare=direct.total_fare + 200,  # Add waiting cost
                fare_breakdown={**direct.fare_breakdown, 'waiting': 200},
                comfort_score=min(1.0, direct.comfort_score + 0.2),  # Better comfort
                crowd_level='low',  # After wait, less crowd
                crowd_avoidance_score=min(1.0, direct.crowd_avoidance_score + 0.3),
                train_numbers=direct.train_numbers,
                seat_class=direct.seat_class,
                seat_available=True
            )
            
            wait_options.append(wait_option)
        
        return wait_options
    
    async def _create_multimodal_options(
        self,
        request: TravelRequest
    ) -> List[TravelOption]:
        """Create multi-modal options"""
        try:
            multimodal = self._get_service("multimodal")
            
            from services.multimodal_planning_service import (
                JourneySearchRequest, ComfortLevel
            )
            
            mm_request = JourneySearchRequest(
                origin=request.origin,
                destination=request.destination,
                travel_date=request.travel_date,
                passenger_count=request.passenger_count,
                max_duration_hours=request.max_wait_hours,
                max_cost=request.max_cost,
                comfort_preference=ComfortLevel.STANDARD,
                avoid_high_crowd=request.avoid_high_crowd
            )
            
            journeys = await multimodal.search_journeys(mm_request)
            
            options = []
            for journey in journeys[:3]:
                option = TravelOption(
                    option_id=f"mm_opt_{journey.journey_id}",
                    option_type="multi_modal",
                    from_station=journey.origin,
                    to_station=journey.destination,
                    departure_time=journey.segments[0].departure if journey.segments else datetime.utcnow(),
                    arrival_time=journey.segments[-1].arrival if journey.segments else datetime.utcnow(),
                    total_duration_minutes=journey.total_duration_minutes,
                    total_fare=journey.total_fare,
                    fare_breakdown={'total': journey.total_fare},
                    comfort_score=journey.comfort_score,
                    crowd_level='low',  # Assume multi-modal is less crowded
                    crowd_avoidance_score=journey.crowd_avoidance_score,
                    segments=[{
                        'mode': s.mode,
                        'from': s.from_location,
                        'to': s.to_location,
                        'fare': s.fare
                    } for s in journey.segments]
                )
                options.append(option)
            
            return options
            
        except Exception as e:
            logger.debug(f"Multi-modal search failed: {e}")
            return []
    
    def _filter_options(
        self,
        options: List[TravelOption],
        request: TravelRequest
    ) -> List[TravelOption]:
        """Filter options based on constraints"""
        filtered = []
        
        for opt in options:
            # Duration filter
            max_duration = (request.max_wait_hours + 4) * 60  # Add some buffer
            if opt.total_duration_minutes > max_duration:
                continue
            
            # Cost filter
            if opt.total_fare > request.max_cost:
                continue
            
            # Crowd filter
            if request.avoid_high_crowd and opt.crowd_level in ['critical', 'full']:
                continue
            
            filtered.append(opt)
        
        return filtered
    
    def _rank_options(
        self,
        options: List[TravelOption],
        request: TravelRequest
    ) -> List[TravelOption]:
        """Rank options based on preference"""
        
        def score_option(opt: TravelOption) -> float:
            score = 0.0
            
            if request.travel_preference == TravelPreference.FASTEST:
                # Faster is better
                max_duration = max(o.total_duration_minutes for o in options) if options else 1
                score += (1.0 - opt.total_duration_minutes / max_duration) * 40
            
            elif request.travel_preference == TravelPreference.CHEAPEST:
                # Cheaper is better
                max_fare = max(o.total_fare for o in options) if options else 1
                score += (1.0 - opt.total_fare / max_fare) * 40
            
            elif request.travel_preference == TravelPreference.COMFORTABLE:
                # More comfortable is better
                score += opt.comfort_score * 40
            
            elif request.travel_preference == TravelPreference.CROWD_FREE:
                # Less crowd is better
                score += opt.crowd_avoidance_score * 40
            
            else:  # BALANCED
                # Balance all factors
                max_duration = max(o.total_duration_minutes for o in options) if options else 1
                max_fare = max(o.total_fare for o in options) if options else 1
                
                time_score = (1.0 - opt.total_duration_minutes / max_duration) * 10
                cost_score = (1.0 - opt.total_fare / max_fare) * 10
                comfort_score = opt.comfort_score * 10
                crowd_score = opt.crowd_avoidance_score * 10
                
                score = time_score + cost_score + comfort_score + crowd_score
            
            # Bonus for recommended type
            if opt.option_type == "direct":
                score += 5
            elif opt.option_type == "wait":
                score += 3
            
            return score
        
        # Sort by score
        options.sort(key=score_option, reverse=True)
        return options
    
    def _get_recommendation_reason(
        self,
        option: TravelOption,
        request: TravelRequest
    ) -> str:
        """Generate recommendation reason"""
        reasons = []
        
        if request.travel_preference == TravelPreference.FASTEST:
            reasons.append(f"Fastest option: {option.total_duration_minutes} minutes")
        elif request.travel_preference == TravelPreference.CHEAPEST:
            reasons.append(f"Best price: ₹{option.total_fare}")
        elif request.travel_preference == TravelPreference.COMFORTABLE:
            reasons.append(f"Most comfortable: {int(option.comfort_score * 100)}% comfort")
        elif request.travel_preference == TravelPreference.CROWD_FREE:
            reasons.append(f"Least crowded: {option.crowd_level} level")
        else:
            if option.crowd_avoidance_score > 0.7:
                reasons.append("Low crowd - comfortable journey")
            if option.comfort_score > 0.8:
                reasons.append("High comfort rating")
            if option.total_fare < 1000:
                reasons.append("Good value for money")
        
        return ". ".join(reasons) if reasons else "Best balance of time, cost, and comfort"
    
    async def _record_search(self, request: TravelRequest, plan: TravelPlan):
        """Record search for analytics"""
        try:
            data_service = self._services.get('algorithm_data')
            if not data_service:
                from services.algorithm_data_service import get_algorithm_data_service
                data_service = get_algorithm_data_service(self.db)
                self._services['algorithm_data'] = data_service
            
            data_service.record_search_event(
                request.origin,
                request.destination,
                request.travel_date
            )
        except Exception as e:
            logger.debug(f"Failed to record search: {e}")
    
    # =========================================================================
    # ADDITIONAL METHODS
    # =========================================================================
    
    async def get_station_amenities(self, station_code: str) -> Dict:
        """Get station amenities"""
        amenity_service = self._get_service("amenity")
        return await amenity_service.get_station_amenities(station_code)
    
    async def book_waiting(
        self,
        passenger_id: str,
        station_code: str,
        package_id: str,
        start_time: datetime,
        passenger_count: int = 1
    ) -> Dict:
        """Book waiting package"""
        amenity_service = self._get_service("amenity")
        booking = await amenity_service.book_waiting(
            passenger_id, station_code, package_id, start_time, passenger_count
        )
        return {
            'booking_id': booking.booking_id,
            'status': booking.status,
            'amount_paid': booking.amount_paid,
            'start_time': booking.start_time.isoformat(),
            'end_time': booking.end_time.isoformat()
        }
    
    async def get_crowd_analysis(self) -> Dict:
        """Get network-wide crowd analysis"""
        crowd_service = self._get_service("crowd")
        return await crowd_service.analyze_network_demand()
    
    async def create_redistribution_offer(
        self,
        passenger_id: str,
        booking_id: str,
        original_train: str,
        alternative_train: str,
        incentive: float = 0.0
    ) -> Dict:
        """Create redistribution offer"""
        crowd_service = self._get_service("crowd")
        offer = await crowd_service.create_redistribution_offer(
            passenger_id, booking_id, original_train, alternative_train, incentive
        )
        return {
            'offer_id': offer.offer_id,
            'original_train': offer.original_train,
            'alternative_train': offer.alternative_train,
            'incentive': offer.incentive_amount,
            'expires_at': offer.expires_at.isoformat()
        }


# Global instance
_travel_planner: Optional[UnifiedTravelPlanner] = None

def get_travel_planner(db=None) -> UnifiedTravelPlanner:
    """Get or create global travel planner"""
    global _travel_planner
    if _travel_planner is None:
        _travel_planner = UnifiedTravelPlanner(db)
    return _travel_planner


# Convenience function for quick access
async def plan_journey(
    origin: str,
    destination: str,
    travel_date: date,
    passenger_count: int = 1,
    preference: str = "balanced",
    max_wait_hours: int = 6,
    max_cost: float = 10000,
    user_id: str = None
) -> Dict:
    """
    Quick function to plan a journey.
    
    Example:
        result = await plan_journey(
            origin="NDLS",
            destination="BCT", 
            travel_date=date(2024, 12, 25),
            passenger_count=2,
            preference="balanced"
        )
    """
    # Convert preference string to enum
    pref_map = {
        'fastest': TravelPreference.FASTEST,
        'cheapest': TravelPreference.CHEAPEST,
        'comfortable': TravelPreference.COMFORTABLE,
        'crowd_free': TravelPreference.CROWD_FREE,
        'balanced': TravelPreference.BALANCED
    }
    
    request = TravelRequest(
        origin=origin,
        destination=destination,
        travel_date=travel_date,
        passenger_count=passenger_count,
        travel_preference=pref_map.get(preference, TravelPreference.BALANCED),
        max_wait_hours=max_wait_hours,
        max_cost=max_cost,
        user_id=user_id
    )
    
    planner = get_travel_planner()
    plan = await planner.create_travel_plan(request)
    
    return plan.to_dict()