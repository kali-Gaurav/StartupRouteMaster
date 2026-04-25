"""
Multi-Modal Travel Planning Service
====================================

This service enables complete journey planning across multiple transport modes:
- Trains (Indian Railways)
- Buses (State transport, private)
- Flights (Domestic)
- Cabs (For first/last mile)
- Metro (Where available)

The system optimizes for:
1. Total journey time
2. Total cost
3. Comfort level
4. Crowd avoidance
5. Accessibility

This is a key component of the crowd control system - by offering
alternatives, we can distribute demand across modes.

Author: Algorithm Team
Version: 1.0.0
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class JourneyType(Enum):
    """Types of multi-modal journeys"""
    TRAIN_ONLY = "train_only"
    TRAIN_BUS = "train_bus"
    TRAIN_FLIGHT = "train_flight"
    BUS_ONLY = "bus_only"
    FLIGHT_ONLY = "flight_only"
    TRAIN_CAB = "train_cab"
    MULTI_MODAL = "multi_modal"  # 3+ modes


class ComfortLevel(Enum):
    """Journey comfort levels"""
    BASIC = "basic"         # Lowest cost, longest time
    STANDARD = "standard"   # Balance
    PREMIUM = "premium"     # Highest comfort
    LUXURY = "luxury"       # VIP service


@dataclass
class ModeSegment:
    """A single segment of a multi-modal journey"""
    segment_id: str
    mode: str  # train, bus, flight, cab, metro
    operator: str  # IRCTC, UPSRTC, Indigo, Ola, etc.
    
    # Route
    from_location: str
    to_location: str
    from_code: str  # Station code
    to_code: str
    
    # Timing
    departure: datetime
    arrival: datetime
    duration_minutes: int
    
    # Cost and Availability (required - must come before optional fields)
    fare: float
    seats_available: int
    
    # Optional fields
    currency: str = "INR"
    seat_class: str = "general"
    comfort_level: ComfortLevel = ComfortLevel.STANDARD
    amenities: List[str] = field(default_factory=list)
    predicted_occupancy: float = 0.5


@dataclass
class MultiModalJourney:
    """
    Complete multi-modal journey from origin to destination.
    """
    journey_id: str
    journey_type: JourneyType
    
    # Endpoints
    origin: str
    destination: str
    travel_date: date
    
    # Segments
    segments: List[ModeSegment] = field(default_factory=list)
    
    # Summary
    total_duration_minutes: int = 0
    total_distance_km: float = 0
    total_fare: float = 0
    
    # Transfer points
    transfer_points: List[str] = field(default_factory=list)
    total_wait_time_minutes: int = 0
    
    # Overall assessment
    comfort_score: float = 0.0
    crowd_avoidance_score: float = 0.0
    value_score: float = 0.0
    
    # Recommendation
    is_recommended: bool = False
    recommendation_reason: str = ""
    
    def __post_init__(self):
        """Calculate derived fields"""
        if self.segments:
            self.total_duration_minutes = sum(s.duration_minutes for s in self.segments)
            self.total_fare = sum(s.fare for s in self.segments)
            self.transfer_points = [s.to_location for s in self.segments[:-1]]
            
            # Calculate comfort score
            comfort_values = {
                ComfortLevel.BASIC: 0.3,
                ComfortLevel.STANDARD: 0.6,
                ComfortLevel.PREMIUM: 0.8,
                ComfortLevel.LUXURY: 1.0
            }
            self.comfort_score = sum(
                comfort_values.get(s.comfort_level, 0.5) for s in self.segments
            ) / len(self.segments)
            
            # Calculate crowd avoidance (inverse of average occupancy)
            avg_occupancy = sum(s.predicted_occupancy for s in self.segments) / len(self.segments)
            self.crowd_avoidance_score = 1.0 - avg_occupancy
            
            # Value score (comfort per rupee)
            if self.total_fare > 0:
                self.value_score = self.comfort_score / (self.total_fare / 100)


@dataclass
class JourneySearchRequest:
    """Request for multi-modal journey search"""
    origin: str
    destination: str
    travel_date: date
    passenger_count: int = 1
    
    # Preferences
    max_duration_hours: int = 24
    max_cost: float = 10000
    preferred_modes: List[str] = field(default_factory=lambda: ["train", "bus", "flight"])
    comfort_preference: ComfortLevel = ComfortLevel.STANDARD
    
    # Crowd preferences
    avoid_high_crowd: bool = True
    allow_wait: bool = True
    max_wait_hours: int = 4
    
    # Accessibility
    requires_accessibility: bool = False
    needs_assistance: bool = False


class MultiModalPlanningService:
    """
    Service for planning multi-modal journeys.
    
    Key features:
    1. Search across all transport modes
    2. Optimize for multiple criteria
    3. Consider crowd levels
    4. Enable first/last mile connectivity
    5. Provide complete journey options
    """
    
    # Mode preferences by distance
    MODE_BY_DISTANCE = [
        (0, 50, ["cab", "bus"]),      # < 50km: cab or bus
        (50, 200, ["bus", "train"]),  # 50-200km: bus or train
        (200, 500, ["train", "bus"]), # 200-500km: train or bus
        (500, 1000, ["train", "flight"]), # 500-1000km: train or flight
        (1000, 99999, ["flight", "train"]) # > 1000km: flight preferred
    ]
    
    def __init__(self, db=None):
        self.db = db
        self._mode_providers = {}
        self.providers = {}  # Transport mode providers
        self.journey_optimizer = None  # Journey optimizer
    
    async def search_journeys(
        self,
        request: JourneySearchRequest
    ) -> List[MultiModalJourney]:
        """
        Search for multi-modal journeys between origin and destination.
        
        Returns list of journey options sorted by recommendation score.
        """
        journeys = []
        
        # Get distance estimate
        distance = await self._estimate_distance(
            request.origin, request.destination
        )
        
        # Determine which modes to search
        modes_to_search = self._determine_modes(distance, request.preferred_modes)
        
        # Search each mode
        for mode in modes_to_search:
            mode_journeys = await self._search_mode(
                mode, request, distance
            )
            journeys.extend(mode_journeys)
        
        # Search multi-modal combinations
        if len(modes_to_search) > 1 and request.max_duration_hours > 4:
            multimodal = await self._search_multimodal(request, distance)
            journeys.extend(multimodal)
        
        # Filter and rank
        journeys = self._filter_journeys(journeys, request)
        journeys = self._rank_journeys(journeys, request)
        
        # Mark recommended
        if journeys:
            journeys[0].is_recommended = True
            journeys[0].recommendation_reason = self._get_recommendation(
                journeys[0], request
            )
        
        return journeys
    
    async def _estimate_distance(self, origin: str, destination: str) -> float:
        """Estimate distance between two locations"""
        # Would use actual distance API
        # For now, use heuristic based on known routes
        return 500.0  # Default estimate
    
    def _determine_modes(
        self,
        distance: float,
        preferred_modes: List[str]
    ) -> List[str]:
        """Determine which modes to search based on distance"""
        modes = []
        
        for min_dist, max_dist, mode_list in self.MODE_BY_DISTANCE:
            if min_dist <= distance < max_dist:
                modes = mode_list
                break
        
        # Filter by preferences
        if preferred_modes:
            modes = [m for m in modes if m in preferred_modes]
        
        return modes if modes else ["train"]
    
    async def _search_mode(
        self,
        mode: str,
        request: JourneySearchRequest,
        distance: float
    ) -> List[MultiModalJourney]:
        """Search for journeys using a specific mode"""
        journeys = []
        
        try:
            if mode == "train":
                journeys = await self._search_trains(request)
            elif mode == "bus":
                journeys = await self._search_buses(request)
            elif mode == "flight":
                journeys = await self._search_flights(request)
            elif mode == "cab":
                journeys = await self._search_cabs(request)
        except Exception as e:
            logger.error(f"Failed to search {mode}: {e}")
        
        return journeys
    
    async def _search_trains(self, request: JourneySearchRequest) -> List[MultiModalJourney]:
        """Search for train journeys"""
        try:
            from services.search_service import SearchService
            
            search_service = SearchService(db=self.db)
            
            result = await search_service.search_routes(
                source=request.origin,
                destination=request.destination,
                travel_date=request.travel_date.isoformat()
            )
            
            journeys = []
            for route in result.get('data', {}).get('journeys', [])[:5]:
                segment = ModeSegment(
                    segment_id=f"seg_train_{route.get('train_number', 'unknown')}",
                    mode="train",
                    operator="Indian Railways",
                    from_location=request.origin,
                    to_location=request.destination,
                    from_code=request.origin,
                    to_code=request.destination,
                    departure=route.get('departure', datetime.utcnow()),
                    arrival=route.get('arrival', datetime.utcnow()),
                    duration_minutes=route.get('duration', 0),
                    fare=route.get('fare', 500),
                    seats_available=route.get('availability', 50),
                    comfort_level=ComfortLevel.STANDARD,
                    predicted_occupancy=route.get('occupancy', 0.5)
                )
                
                journey = MultiModalJourney(
                    journey_id=f"journey_{segment.segment_id}",
                    journey_type=JourneyType.TRAIN_ONLY,
                    origin=request.origin,
                    destination=request.destination,
                    travel_date=request.travel_date,
                    segments=[segment]
                )
                
                journeys.append(journey)
            
            return journeys
            
        except Exception as e:
            logger.error(f"Train search failed: {e}")
            return []
    
    async def _search_buses(self, request: JourneySearchRequest) -> List[MultiModalJourney]:
        """Search for bus journeys"""
        # Would integrate with bus API
        # For now, return empty
        return []
    
    async def _search_flights(self, request: JourneySearchRequest) -> List[MultiModalJourney]:
        """Search for flight journeys"""
        # Would integrate with flight API
        return []
    
    async def _search_cabs(self, request: JourneySearchRequest) -> List[MultiModalJourney]:
        """Search for cab options"""
        # Would integrate with cab API
        return []
    
    async def _search_multimodal(
        self,
        request: JourneySearchRequest,
        distance: float
    ) -> List[MultiModalJourney]:
        """Search for multi-modal journeys (train + bus, etc.)"""
        journeys = []
        
        # Example: Train to hub + Bus to destination
        # This would require finding hub stations
        
        return journeys
    
    def _filter_journeys(
        self,
        journeys: List[MultiModalJourney],
        request: JourneySearchRequest
    ) -> List[MultiModalJourney]:
        """Filter journeys based on constraints"""
        filtered = []
        
        for journey in journeys:
            # Duration filter
            if journey.total_duration_minutes > request.max_duration_hours * 60:
                continue
            
            # Cost filter
            if journey.total_fare > request.max_cost:
                continue
            
            # Crowd avoidance
            if request.avoid_high_crowd and journey.crowd_avoidance_score < 0.3:
                continue
            
            # Accessibility
            if request.requires_accessibility:
                # Check if all segments are accessible
                accessible = all(
                    'accessible' in s.amenities or s.comfort_level in [ComfortLevel.PREMIUM, ComfortLevel.LUXURY]
                    for s in journey.segments
                )
                if not accessible:
                    continue
            
            filtered.append(journey)
        
        return filtered
    
    def _rank_journeys(
        self,
        journeys: List[MultiModalJourney],
        request: JourneySearchRequest
    ) -> List[MultiModalJourney]:
        """Rank journeys based on preferences"""
        
        def score_journey(j: MultiModalJourney) -> float:
            score = 0.0
            
            # Time score (faster is better)
            max_duration = request.max_duration_hours * 60
            time_score = 1.0 - (j.total_duration_minutes / max_duration)
            score += time_score * 0.3
            
            # Cost score (cheaper is better)
            cost_score = 1.0 - (j.total_fare / request.max_cost)
            score += cost_score * 0.2
            
            # Comfort score
            score += j.comfort_score * 0.25
            
            # Crowd avoidance
            if request.avoid_high_crowd:
                score += j.crowd_avoidance_score * 0.25
            
            return score
        
        # Sort by score
        journeys.sort(key=score_journey, reverse=True)
        
        return journeys
    
    def _get_recommendation(
        self,
        journey: MultiModalJourney,
        request: JourneySearchRequest
    ) -> str:
        """Generate recommendation reason"""
        reasons = []
        
        if journey.journey_type == JourneyType.TRAIN_ONLY:
            reasons.append("Direct train available")
        elif journey.journey_type == JourneyType.MULTI_MODAL:
            reasons.append("Multi-modal journey with better availability")
        
        if journey.crowd_avoidance_score > 0.7:
            reasons.append("Low crowd - comfortable journey")
        
        if journey.comfort_score > 0.7:
            reasons.append("High comfort rating")
        
        if journey.total_fare < request.max_cost * 0.7:
            reasons.append("Good value for money")
        
        return ". ".join(reasons) if reasons else "Best option based on your preferences"
    
    # =========================================================================
    # FIRST/LAST MILE CONNECTIVITY
    # =========================================================================
    
    async def get_first_last_mile_options(
        self,
        location: str,
        is_origin: bool
    ) -> Dict[str, List[Dict]]:
        """
        Get first/last mile connectivity options.
        Helps complete the journey from home to station/airport.
        """
        options = {
            'cab': [],
            'auto': [],
            'metro': [],
            'bus': []
        }
        
        # Would integrate with cab APIs (Ola, Uber)
        # Would integrate with metro where available
        
        # For demo, return structure
        if is_origin:
            options['cab'].append({
                'type': 'cab',
                'operator': 'Ola/Uber',
                'estimated_time': 15,
                'estimated_cost': 150,
                'available': True
            })
            options['auto'].append({
                'type': 'auto',
                'estimated_time': 20,
                'estimated_cost': 80,
                'available': True
            })
        
        return options
    
    # =========================================================================
    # JOURNEY OPTIMIZATION
    # =========================================================================
    
    async def optimize_journey(
        self,
        journey: MultiModalJourney,
        optimization_goal: str = "balanced"
    ) -> MultiModalJourney:
        """
        Optimize a journey based on specific goals.
        
        Goals:
        - fastest: Minimize total time
        - cheapest: Minimize cost
        - most_comfortable: Maximize comfort
        - crowd_free: Minimize crowd
        - balanced: Balance all factors
        """
        
        if optimization_goal == "fastest":
            # Already sorted by duration
            return journey
        
        elif optimization_goal == "cheapest":
            # Would adjust for lower cost options
            return journey
        
        elif optimization_goal == "most_comfortable":
            # Would prioritize premium options
            return journey
        
        elif optimization_goal == "crowd_free":
            # Would prioritize less crowded options
            return journey
        
        else:  # balanced
            return journey


# Global instance
_multimodal_service: Optional[MultiModalPlanningService] = None

def get_multimodal_planning_service(db=None) -> MultiModalPlanningService:
    """Get or create global multimodal service"""
    global _multimodal_service
    if _multimodal_service is None:
        _multimodal_service = MultiModalPlanningService(db)
    return _multimodal_service