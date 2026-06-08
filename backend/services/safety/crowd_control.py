"""
Crowd Control & Demand Redistribution Service
==============================================

Patent Innovation: Demand-Based Passenger Redistribution System

This service addresses the critical problem of crowd management in Indian Railways:
1. Real-time crowd monitoring at stations and trains
2. Predictive demand modeling
3. Multi-modal passenger redistribution
4. Smart travel planning with wait options
5. Station amenity integration

Core Philosophy:
- Instead of just booking the first available train, offer complete travel plans
- Allow passengers to wait at better-equipped stations
- Distribute demand across time and routes
- Provide premium waiting services
- Enable multi-modal journeys

Author: Algorithm Team
Version: 1.0.0
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CrowdLevel(Enum):
    """Station/Train crowd levels"""
    LOW = "low"           # < 30% capacity
    MODERATE = "moderate" # 30-60% capacity
    HIGH = "high"         # 60-85% capacity
    CRITICAL = "critical" # > 85% capacity
    FULL = "full"         # 100%+ (overcrowded)


class TransportMode(Enum):
    """Available transport modes"""
    TRAIN = "train"
    BUS = "bus"
    FLIGHT = "flight"
    CAB = "cab"
    METRO = "metro"


class WaitOption(Enum):
    """Passenger wait preferences"""
    NO_WAIT = "no_wait"           # Must travel immediately
    SHORT_WAIT = "short_wait"     # 0-2 hours
    MEDIUM_WAIT = "medium_wait"   # 2-6 hours
    LONG_WAIT = "long_wait"       # 6-24 hours
    FLEXIBLE = "flexible"         # Any wait acceptable


@dataclass
class StationCrowdData:
    """Real-time crowd data for a station"""
    station_code: str
    station_name: str
    current_crowd_level: CrowdLevel
    waiting_passengers: int
    platform_capacity: int
    avg_wait_time_minutes: int
    next_train_available: Optional[datetime]
    amenities_score: float  # 0-1 (food, lounge, etc.)
    
    # Historical patterns
    peak_hours: List[int] = field(default_factory=list)
    avg_daily_passengers: int = 0
    
    # Predictions
    predicted_crowd_next_1h: CrowdLevel = CrowdLevel.LOW
    predicted_crowd_next_3h: CrowdLevel = CrowdLevel.LOW


@dataclass
class TrainCrowdData:
    """Real-time crowd data for a train"""
    train_number: str
    train_name: str
    source: str
    destination: str
    departure_time: datetime
    
    # Capacity analysis
    total_seats: int
    booked_seats: int
    rac_count: int
    wl_count: int
    
    # Crowd level
    crowd_level: CrowdLevel
    occupancy_rate: float
    
    # Coach-wise distribution
    coach_occupancy: Dict[str, float] = field(default_factory=dict)
    
    # Predictions
    predicted_occupancy_at_departure: float = 0.0
    cancellation_probability: float = 0.0


@dataclass
class TravelPlan:
    """
    Complete travel plan for a passenger.
    Instead of just booking a single train, this provides
    optimized multi-segment journey options.
    """
    plan_id: str
    source: str
    destination: str
    travel_date: date
    
    # Segments (can be multiple if waiting)
    segments: List['TravelSegment'] = field(default_factory=list)
    
    # Wait information
    total_wait_time_minutes: int = 0
    wait_station: Optional[str] = None
    wait_amenities: Dict[str, Any] = field(default_factory=dict)
    
    # Options offered
    options: List['TravelOption'] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    
    @property
    def total_journey_time(self) -> int:
        """Total journey time including waits"""
        travel_time = sum(s.duration_minutes for s in self.segments)
        return travel_time + self.total_wait_time_minutes
    
    @property
    def has_wait(self) -> bool:
        """Whether this plan involves waiting"""
        return self.total_wait_time_minutes > 0


@dataclass
class TravelSegment:
    """Single segment of a journey"""
    segment_id: str
    mode: TransportMode
    from_station: str
    to_station: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    train_number: Optional[str] = None
    seat_class: str = "SL"
    fare: float = 0.0
    seat_available: bool = True
    coach: Optional[str] = None
    seat: Optional[str] = None


@dataclass
class TravelOption:
    """
    A single travel option within a plan.
    Passenger can choose from multiple options.
    """
    option_id: str
    option_type: str  # "direct", "wait", "multi_modal", "alternative_route"
    
    # Timing
    departure_time: datetime
    arrival_time: datetime
    total_duration_minutes: int
    
    # Cost (required - must come before optional fields)
    total_fare: float
    comfort_score: float  # 0-1
    
    # Optional fields
    wait_time_minutes: int = 0
    fare_breakdown: Dict[str, float] = field(default_factory=dict)
    crowd_level_at_departure: CrowdLevel = CrowdLevel.LOW
    is_recommended: bool = False
    recommendation_reason: str = ""
    alternatives: List[str] = field(default_factory=list)


@dataclass
class RedistributionOffer:
    """
    Offer to passenger for redistribution.
    Part of the patent innovation for crowd control.
    """
    offer_id: str
    passenger_id: str
    original_booking_id: str
    
    # Original plan
    original_train: str
    original_departure: datetime
    original_fare: float
    
    # Alternative offered
    alternative_train: str
    alternative_departure: datetime
    alternative_fare: float
    
    # Incentive
    incentive_amount: float = 0.0
    incentive_type: str = "cash_credit"  # cash_credit, upgrade, voucher
    
    # Wait details
    wait_station: Optional[str] = None
    wait_duration_minutes: int = 0
    wait_amenities: Dict[str, Any] = field(default_factory=dict)
    
    # Time advantage
    time_difference_minutes: int = 0  # positive = faster
    
    # Status
    status: str = "pending"  # pending, accepted, declined, expired
    expires_at: Optional[datetime] = None


class CrowdControlService:
    """
    Main service for crowd control and demand redistribution.
    
    This is the core patent innovation that addresses:
    1. Station crowding
    2. Train overloading
    3. Waitlist management
    4. Multi-modal integration
    
    The system works by:
    1. Continuously monitoring crowd levels
    2. Predicting future demand
    3. Identifying redistribution opportunities
    4. Offering incentives to flexible passengers
    5. Providing complete travel plans with wait options
    """
    
    # Configuration
    CROWD_THRESHOLDS = {
        CrowdLevel.LOW: 0.3,
        CrowdLevel.MODERATE: 0.6,
        CrowdLevel.HIGH: 0.85,
        CrowdLevel.CRITICAL: 0.95,
        CrowdLevel.FULL: 1.0
    }
    
    # Wait time thresholds (minutes)
    SHORT_WAIT_MAX = 120
    MEDIUM_WAIT_MAX = 360
    LONG_WAIT_MAX = 1440
    
    def __init__(self, db: Optional[Session] = None):
        self.db: Optional[Session] = db
        self._station_data: Dict[str, StationCrowdData] = {}
        self._train_data: Dict[str, TrainCrowdData] = {}
        self._last_update: Optional[datetime] = None
    
    @staticmethod
    def _get_crowd_level(occupancy_rate: float) -> 'CrowdLevel':
        """
        Convert occupancy rate to CrowdLevel enum.
        
        Args:
            occupancy_rate: Rate between 0 and 1
            
        Returns:
            Corresponding CrowdLevel
        """
        if occupancy_rate < 0.3:
            return CrowdLevel.LOW
        elif occupancy_rate < 0.6:
            return CrowdLevel.MODERATE
        elif occupancy_rate < 0.85:
            return CrowdLevel.HIGH
        elif occupancy_rate <= 0.95:
            return CrowdLevel.CRITICAL
        else:
            return CrowdLevel.FULL
    
    # =========================================================================
    # CROWD MONITORING
    # =========================================================================
    
    async def get_station_crowd(self, station_code: str) -> StationCrowdData:
        """
        Get current crowd data for a station.
        Uses cached data with periodic refresh.
        """
        # Check cache
        if station_code in self._station_data and self._last_update is not None:
            cache_age = (datetime.utcnow() - self._last_update).total_seconds()
            if cache_age < 300:  # 5 minutes cache
                return self._station_data[station_code]
        
        # Fetch fresh data
        data = await self._fetch_station_crowd(station_code)
        self._station_data[station_code] = data
        self._last_update = datetime.utcnow()
        
        return data
    
    async def _fetch_station_crowd(self, station_code: str) -> StationCrowdData:
        """Fetch station crowd data from various sources"""
        try:
            if self.db is None:
                raise RuntimeError("Database session is required to fetch station crowd data")

            # Get station info
            from services.stations.service import StationService
            station_service = StationService(self.db)
            station_info = station_service.get_station(station_code)
            
            # Get current bookings for this station
            from services.data.algorithm_data import get_algorithm_data_service
            data_service = get_algorithm_data_service(self.db)
            
            # Get demand snapshot
            demand = data_service.get_demand_snapshot(
                station_code, "%", date.today()
            )
            
            # Calculate crowd level
            waiting = demand.get('bookings', 0) if demand else 0
            capacity = station_info.get('platform_capacity', 1000) if station_info else 1000
            crowd_level = self._calculate_crowd_level(waiting, capacity)
            
            # Get amenities score
            amenities_score = await self._get_station_amenities_score(station_code)
            
            return StationCrowdData(
                station_code=station_code,
                station_name=station_info.get('name', station_code) if station_info else station_code,
                current_crowd_level=crowd_level,
                waiting_passengers=waiting,
                platform_capacity=capacity,
                avg_wait_time_minutes=self._estimate_wait_time(crowd_level),
                next_train_available=await self._get_next_train(station_code),
                amenities_score=amenities_score,
                peak_hours=station_info.get('peak_hours', []) if station_info else [],
                avg_daily_passengers=station_info.get('daily_passengers', 0) if station_info else 0
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch station crowd data: {e}")
            # Return default data
            return StationCrowdData(
                station_code=station_code,
                station_name=station_code,
                current_crowd_level=CrowdLevel.MODERATE,
                waiting_passengers=0,
                platform_capacity=1000,
                avg_wait_time_minutes=30,
                next_train_available=None,
                amenities_score=0.5
            )
    
    def _calculate_crowd_level(self, current: int, capacity: int) -> CrowdLevel:
        """Calculate crowd level from numbers"""
        if capacity == 0:
            return CrowdLevel.MODERATE
        
        rate = current / capacity
        
        if rate < self.CROWD_THRESHOLDS[CrowdLevel.LOW]:
            return CrowdLevel.LOW
        elif rate < self.CROWD_THRESHOLDS[CrowdLevel.MODERATE]:
            return CrowdLevel.MODERATE
        elif rate < self.CROWD_THRESHOLDS[CrowdLevel.HIGH]:
            return CrowdLevel.HIGH
        elif rate < self.CROWD_THRESHOLDS[CrowdLevel.CRITICAL]:
            return CrowdLevel.CRITICAL
        else:
            return CrowdLevel.FULL
    
    async def _get_station_amenities_score(self, station_code: str) -> float:
        """Calculate station amenities score (0-1)"""
        # This would integrate with station service
        # For now, return based on station tier
        tier1_stations = ['NDLS', 'BCT', 'HWH', 'MAS', 'SBC', 'CSMT', 'ADI', 'JP']
        tier2_stations = ['DDN', 'CNB', 'BPL', 'PUNE', 'GUW', 'KOL']
        
        if station_code in tier1_stations:
            return 0.9
        elif station_code in tier2_stations:
            return 0.7
        else:
            return 0.5
    
    async def _get_next_train(self, station_code: str) -> Optional[datetime]:
        """Get next available train from station"""
        # Simplified - would query actual schedule
        return datetime.utcnow() + timedelta(minutes=30)
    
    def _estimate_wait_time(self, crowd_level: CrowdLevel) -> int:
        """Estimate average wait time based on crowd level"""
        wait_times = {
            CrowdLevel.LOW: 15,
            CrowdLevel.MODERATE: 30,
            CrowdLevel.HIGH: 60,
            CrowdLevel.CRITICAL: 120,
            CrowdLevel.FULL: 240
        }
        return wait_times.get(crowd_level, 30)
    
    async def get_train_crowd(self, train_number: str, travel_date: date) -> TrainCrowdData:
        """Get crowd data for a specific train"""
        cache_key = f"{train_number}:{travel_date.isoformat()}"
        
        if cache_key in self._train_data:
            return self._train_data[cache_key]
        
        # Fetch from database
        data = await self._fetch_train_crowd(train_number, travel_date)
        self._train_data[cache_key] = data
        
        return data
    
    async def _fetch_train_crowd(self, train_number: str, travel_date: date) -> TrainCrowdData:
        """Fetch train crowd data"""
        try:
            from database.models.core import Booking
            from services.ml.cancellation import CancellationPredictor
            bookings = []
            if self.db is not None:
                bookings = self.db.query(Booking).filter(
                    Booking.train_number == train_number,
                    Booking.travel_date == travel_date,
                    Booking.booking_status.in_(['confirmed', 'pending'])
                ).all()
            total_capacity = 1000  # Default for now
            booked = len(bookings)
            rac = sum(1 for b in bookings if b.booking_status == 'RAC')
            wl = sum(1 for b in bookings if b.booking_status == 'WL')
            occupancy_rate = booked / total_capacity if total_capacity > 0 else 0
            crowd_level = self._calculate_crowd_level(booked, total_capacity)
            predictor = CancellationPredictor()
            cancel_pred = predictor.predict_cancellation_rate(
                train_id=int(train_number) if str(train_number).isdigit() else 0,
                travel_date=travel_date.isoformat(),
                quota_type="general",
                days_to_departure=max(0, (travel_date - date.today()).days),
                booking_velocity=0.0,
                route_popularity=0.0,
                demand_forecast=0.0,
                historical_cancellation_rate=0.0
            )
            return TrainCrowdData(
                train_number=train_number,
                train_name=f"Train {train_number}",
                source="",  # Would be populated
                destination="",
                departure_time=datetime.utcnow(),
                total_seats=total_capacity,
                booked_seats=booked,
                rac_count=rac,
                wl_count=wl,
                crowd_level=crowd_level,
                occupancy_rate=occupancy_rate,
                predicted_occupancy_at_departure=occupancy_rate * (1 - getattr(cancel_pred, 'predicted_rate', 0.0)),
                cancellation_probability=getattr(cancel_pred, 'predicted_rate', 0.0)
            )
        except Exception as e:
            logger.error(f"Failed to fetch train crowd data: {e}")
            return TrainCrowdData(
                train_number=train_number,
                train_name=f"Train {train_number}",
                source="",
                destination="",
                departure_time=datetime.utcnow(),
                total_seats=1000,
                booked_seats=0,
                rac_count=0,
                wl_count=0,
                crowd_level=CrowdLevel.MODERATE,
                occupancy_rate=0.5
            )
    
    # =========================================================================
    # SMART TRAVEL PLANNING
    # =========================================================================
    
    async def generate_travel_plan(
        self,
        source: str,
        destination: str,
        travel_date: date,
        passenger_count: int = 1,
        wait_preference: WaitOption = WaitOption.FLEXIBLE,
        max_wait_hours: int = 24
    ) -> TravelPlan:
        """
        Generate complete travel plan with multiple options.
        
        This is the core innovation - instead of just finding
        the first available train, we provide:
        1. Direct option (no wait)
        2. Short wait option
        3. Alternative route option
        4. Multi-modal option
        
        Each option shows crowd levels, amenities, and incentives.
        """
        plan_id = f"plan_{source}_{destination}_{travel_date.isoformat()}"
        
        # Get current station crowd data
        source_crowd = await self.get_station_crowd(source)
        
        # Find all available routes
        routes = await self._find_routes(source, destination, travel_date)
        
        # Generate options from routes
        options = []
        for route in routes:
            option = await self._create_travel_option(
                route, source_crowd, passenger_count, wait_preference, max_wait_hours
            )
            if option:
                options.append(option)
        
        # Sort by recommendation score
        options.sort(key=lambda x: (
            x.is_recommended,
            -x.wait_time_minutes,  # Less wait is better
            x.comfort_score,       # More comfort is better
            x.total_fare           # Lower fare is better
        ), reverse=True)
        
        # Mark top option as recommended
        if options:
            options[0].is_recommended = True
            options[0].recommendation_reason = self._get_recommendation_reason(
                options[0], source_crowd
            )
        
        # Determine wait station if applicable
        wait_station = None
        wait_amenities = {}
        total_wait = 0
        
        if options and options[0].wait_time_minutes > 0:
            # Find best wait station
            wait_station, wait_amenities = await self._find_best_wait_station(
                source, destination, options[0].wait_time_minutes
            )
            total_wait = options[0].wait_time_minutes
        
        return TravelPlan(
            plan_id=plan_id,
            source=source,
            destination=destination,
            travel_date=travel_date,
            options=options,
            total_wait_time_minutes=total_wait,
            wait_station=wait_station,
            wait_amenities=wait_amenities,
            valid_until=datetime.utcnow() + timedelta(minutes=15)
        )
    
    async def _find_routes(
        self,
        source: str,
        destination: str,
        travel_date: date
    ) -> List[Dict]:
        """Find all available routes between source and destination"""
        try:
            if self.db is None:
                raise RuntimeError("Database session is required to search routes")

            from services.search_service import SearchService
            search_service = SearchService(db=self.db)
            
            # Search for routes
            result = await search_service.search_routes(
                source=source,
                destination=destination,
                travel_date=travel_date.isoformat()
            )
            
            routes = result.get('data', {}).get('journeys', [])
            return routes[:10]  # Top 10 routes
            
        except Exception as e:
            logger.error(f"Route search failed: {e}")
            return []
    
    async def _create_travel_option(
        self,
        route: Dict,
        source_crowd: StationCrowdData,
        passenger_count: int,
        wait_preference: WaitOption,
        max_wait_hours: int
    ) -> Optional[TravelOption]:
        """Create a travel option from a route"""
        try:
            # Get train crowd data
            train_number = route.get('train_number', 'UNKNOWN')
            travel_date = route.get('travel_date', date.today())
            
            train_crowd = await self.get_train_crowd(train_number, travel_date)
            
            # Calculate wait time based on crowd
            wait_time = self._calculate_wait_time(
                source_crowd.current_crowd_level,
                train_crowd.crowd_level,
                wait_preference
            )
            
            # Check if wait exceeds preference
            max_wait_minutes = max_wait_hours * 60
            if wait_time > max_wait_minutes:
                return None
            
            # Calculate fare
            base_fare = route.get('fare', 300)
            total_fare = base_fare * passenger_count
            
            # Calculate comfort score
            comfort = self._calculate_comfort_score(
                train_crowd.crowd_level,
                source_crowd.amenities_score,
                wait_time
            )
            
            return TravelOption(
                option_id=f"opt_{train_number}_{datetime.utcnow().timestamp()}",
                option_type="direct" if wait_time == 0 else "wait",
                departure_time=route.get('departure', datetime.utcnow()),
                arrival_time=route.get('arrival', datetime.utcnow()),
                total_duration_minutes=route.get('duration', 0),
                wait_time_minutes=wait_time,
                total_fare=total_fare,
                fare_breakdown={
                    'base': base_fare,
                    'passengers': passenger_count,
                    'total': total_fare
                },
                comfort_score=comfort,
                crowd_level_at_departure=train_crowd.crowd_level
            )
            
        except Exception as e:
            logger.error(f"Failed to create travel option: {e}")
            return None
    
    def _calculate_wait_time(
        self,
        station_crowd: CrowdLevel,
        train_crowd: CrowdLevel,
        preference: WaitOption
    ) -> int:
        """Calculate recommended wait time based on crowd levels"""
        # Base wait from station crowd
        base_wait = {
            CrowdLevel.LOW: 0,
            CrowdLevel.MODERATE: 15,
            CrowdLevel.HIGH: 30,
            CrowdLevel.CRITICAL: 60,
            CrowdLevel.FULL: 120
        }.get(station_crowd, 0)
        
        # Adjust for train crowd
        if train_crowd in [CrowdLevel.CRITICAL, CrowdLevel.FULL]:
            base_wait += 30
        
        # Adjust for preference
        max_wait = {
            WaitOption.NO_WAIT: 0,
            WaitOption.SHORT_WAIT: self.SHORT_WAIT_MAX,
            WaitOption.MEDIUM_WAIT: self.MEDIUM_WAIT_MAX,
            WaitOption.LONG_WAIT: self.LONG_WAIT_MAX,
            WaitOption.FLEXIBLE: 9999
        }.get(preference, 9999)
        
        return min(base_wait, max_wait)
    
    def _calculate_comfort_score(
        self,
        train_crowd: CrowdLevel,
        station_amenities: float,
        wait_time: int
    ) -> float:
        """Calculate comfort score for the journey"""
        # Base from train crowd
        crowd_score = {
            CrowdLevel.LOW: 1.0,
            CrowdLevel.MODERATE: 0.8,
            CrowdLevel.HIGH: 0.6,
            CrowdLevel.CRITICAL: 0.4,
            CrowdLevel.FULL: 0.2
        }.get(train_crowd, 0.5)
        
        # Adjust for station amenities
        amenity_factor = station_amenities * 0.2
        
        # Adjust for wait time (some wait at good station is better than crowded train)
        wait_factor = 0.0
        if wait_time > 0 and station_amenities > 0.7:
            wait_factor = 0.1
        
        return min(1.0, crowd_score + amenity_factor + wait_factor)
    
    async def _find_best_wait_station(
        self,
        source: str,
        destination: str,
        wait_duration: int
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Find best station to wait at"""
        # Find stations along the route with good amenities
        try:
            # Get route stations
            route_stations = await self._get_route_stations(source, destination)
            
            best_station = None
            best_score = 0
            amenities = {}
            
            for station in route_stations:
                if station == source:
                    continue
                crowd = await self.get_station_crowd(station)
                # Score based on amenities and crowd (avoid multiplying enum by float)
                crowd_level_numeric = {
                    CrowdLevel.LOW: 0.0,
                    CrowdLevel.MODERATE: 1.0,
                    CrowdLevel.HIGH: 2.0,
                    CrowdLevel.CRITICAL: 3.0,
                    CrowdLevel.FULL: 4.0
                }[crowd.current_crowd_level]
                score = crowd.amenities_score * (1.0 - crowd_level_numeric * 0.3)
                if score > best_score:
                    best_score = score
                    best_station = station
                    amenities = {
                        'has_lounge': crowd.amenities_score > 0.7,
                        'has_food': crowd.amenities_score > 0.5,
                        'has_wifi': crowd.amenities_score > 0.8,
                        'crowd_level': crowd.current_crowd_level.value,
                        'estimated_wait': wait_duration
                    }
            
            return best_station, amenities
            
        except Exception as e:
            logger.error(f"Failed to find wait station: {e}")
            return None, {}
    
    async def _get_route_stations(self, source: str, destination: str) -> List[str]:
        """Get stations along a route"""
        # Simplified - would use actual route data
        return [source, destination]
    
    def _get_recommendation_reason(
        self,
        option: TravelOption,
        source_crowd: StationCrowdData
    ) -> str:
        """Generate human-readable recommendation reason"""
        reasons = []
        
        if option.wait_time_minutes == 0:
            reasons.append("Direct journey, no waiting")
        elif option.wait_time_minutes < 60:
            reasons.append(f"Short {option.wait_time_minutes}min wait at station with amenities")
        
        if option.crowd_level_at_departure == CrowdLevel.LOW:
            reasons.append("Low crowd on train - comfortable journey")
        elif option.crowd_level_at_departure == CrowdLevel.MODERATE:
            reasons.append("Moderate crowd - manageable")
        
        if option.comfort_score > 0.8:
            reasons.append("High comfort rating")
        
        return ". ".join(reasons) if reasons else "Best balance of time and comfort"
    
    # =========================================================================
    # DEMAND REDISTRIBUTION
    # =========================================================================
    
    async def analyze_network_demand(self) -> Dict[str, Any]:
        """
        Analyze demand across the entire network.
        Identifies:
        - Overcrowded stations
        - Underutilized trains
        - Redistribution opportunities
        """
        # Get all major stations
        major_stations = ['NDLS', 'BCT', 'HWH', 'MAS', 'SBC', 'CSMT', 'ADI', 'JP', 
                         'DDN', 'CNB', 'BPL', 'PUNE', 'GKP', 'MGS', 'ASN']
        
        station_analysis = {}
        
        for station in major_stations:
            crowd = await self.get_station_crowd(station)
            station_analysis[station] = {
                'crowd_level': crowd.current_crowd_level.value,
                'waiting': crowd.waiting_passengers,
                'amenities': crowd.amenities_score,
                'next_train': crowd.next_train_available.isoformat() if crowd.next_train_available else None
            }
        
        # Identify opportunities
        opportunities = self._identify_redistribution_opportunities(station_analysis)
        
        return {
            'stations': station_analysis,
            'opportunities': opportunities,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _identify_redistribution_opportunities(
        self,
        station_analysis: Dict
    ) -> List[Dict]:
        """Identify routes where redistribution could help"""
        opportunities = []
        
        # Find high crowd stations
        high_crowd = [
            s for s, data in station_analysis.items()
            if data['crowd_level'] in ['high', 'critical', 'full']
        ]
        
        # Find low crowd stations
        low_crowd = [
            s for s, data in station_analysis.items()
            if data['crowd_level'] in ['low', 'moderate']
        ]
        
        # Create opportunities
        for high in high_crowd:
            for low in low_crowd:
                if high != low:
                    opportunities.append({
                        'from_station': high,
                        'to_station': low,
                        'reason': f"Redistribute from crowded {high} to less crowded {low}",
                        'potential_passengers': station_analysis[high]['waiting'] // 2
                    })
        
        return opportunities[:10]  # Top 10 opportunities
    
    async def create_redistribution_offer(
        self,
        passenger_id: str,
        original_booking_id: str,
        original_train: str,
        alternative_train: str,
        incentive_amount: float = 0.0
    ) -> RedistributionOffer:
        """Create a redistribution offer for a passenger"""
        
        offer = RedistributionOffer(
            offer_id=f"offer_{datetime.utcnow().timestamp()}",
            passenger_id=passenger_id,
            original_booking_id=original_booking_id,
            original_train=original_train,
            alternative_train=alternative_train,
            original_departure=datetime.utcnow(),
            alternative_departure=datetime.utcnow() + timedelta(hours=2),
            original_fare=500.0,
            alternative_fare=450.0,
            incentive_amount=incentive_amount,
            expires_at=datetime.utcnow() + timedelta(hours=2)
        )
        
        return offer
    
    # =========================================================================
    # STATION AMENITIES
    # =========================================================================
    
    async def get_station_amenities(self, station_code: str) -> Dict[str, Any]:
        """Get available amenities at a station"""
        crowd = await self.get_station_crowd(station_code)
        
        amenities = {
            'station': station_code,
            'crowd_level': crowd.current_crowd_level.value,
            'services': []
        }
        
        # Add services based on amenities score
        if crowd.amenities_score > 0.3:
            amenities['services'].append({
                'type': 'waiting_lounge',
                'available': True,
                'capacity': int(crowd.platform_capacity * 0.1),
                'price_per_hour': 50
            })
        
        if crowd.amenities_score > 0.5:
            amenities['services'].append({
                'type': 'food_court',
                'available': True,
                'options': ['vegetarian', 'non_vegetarian', 'fast_food']
            })
        
        if crowd.amenities_score > 0.7:
            amenities['services'].extend([
                {'type': 'wifi', 'available': True, 'free': True},
                {'type': 'charging_points', 'available': True},
                {'type': 'restrooms', 'available': True},
                {'type': 'medical_assistance', 'available': True}
            ])
        
        # Add language learning (free service)
        amenities['services'].append({
            'type': 'language_learning',
            'available': True,
            'free': True,
            'languages': ['English', 'Hindi', 'Regional']
        })
        
        return amenities


# Global instance
_crowd_control_service: Optional[CrowdControlService] = None

def get_crowd_control_service(db=None) -> CrowdControlService:
    """Get or create global crowd control service"""
    global _crowd_control_service
    if _crowd_control_service is None:
        _crowd_control_service = CrowdControlService(db)
    return _crowd_control_service
