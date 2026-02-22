"""
Smart Seat Allocation Engine
=============================

Implements fair and intelligent seat allocation across multiple coaches.

Features:
- Fair multi-coach distribution
- Berth preference optimization
- Family grouping
- Accessibility consideration
- Overbooking control (5-10% safety margin)

Author: Backend Intelligence System
Date: 2026-02-17
"""

import logging
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import random

logger = logging.getLogger(__name__)


class BerthType(Enum):
    """Berth types in Indian trains."""
    LOWER = "LB"
    UPPER = "UB"
    SIDE_LOWER = "SL"
    SIDE_UPPER = "SU"
    COUPE = "CP"
    NO_PREFERENCE = "NO_PREF"


class CoachType(Enum):
    """Types of coaches."""
    AC_FIRST = "AC1"
    AC_TWO = "AC2"
    AC_THREE = "AC3"
    SLEEPER = "SL"
    GENERAL = "GN"


@dataclass
class BerthPreference:
    """Passenger's preferred berth."""
    berth_type: BerthType = BerthType.NO_PREFERENCE
    accessibility_required: bool = False
    prefer_near_window: bool = False
    prefer_near_corridor: bool = False
    avoid_upper: bool = False


@dataclass
class Seat:
    """Individual seat/berth."""
    berth_id: str  # e.g., "01-LB", "01-UB"
    coach_number: int
    berth_type: BerthType
    is_accessible: bool = False
    is_near_window: bool = False
    is_near_corridor: bool = False
    is_available: bool = True
    allocated_to_pnr: Optional[str] = None
    allocated_passenger_id: Optional[str] = None


@dataclass
class CoachLayout:
    """Configuration of a coach."""
    coach_number: int
    coach_type: CoachType
    total_seats: int
    lower_berths: int
    upper_berths: int
    side_lower_berths: int
    side_upper_berths: int
    accessible_seats: int
    seats: List[Seat] = field(default_factory=list)
    
    def total_seats_count(self) -> int:
        """Total available seats in coach."""
        return self.total_seats
    
    def available_seats_count(self) -> int:
        """Count of currently available seats."""
        return sum(1 for s in self.seats if s.is_available)


@dataclass
class AllocationRequest:
    """Request for seat allocation."""
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    travel_date: str
    num_passengers: int
    passengers: List[Dict]  # [{'name': str, 'berth_preference': BerthPreference}, ...]
    pnr_number: str
    allow_split: bool = False  # Allow splitting across coaches?
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """Validate request."""
        if self.num_passengers <= 0:
            return False, "num_passengers must be > 0"
        if self.num_passengers > 6:
            return False, "Maximum 6 passengers per booking"
        if len(self.passengers) != self.num_passengers:
            return False, "Passenger count mismatch"
        return True, None


@dataclass
class AllocationResult:
    """Result of seat allocation."""
    success: bool
    pnr_number: str
    allocated_seats: List[Seat]
    allocations: List[Dict]  # [{'passenger': str, 'berth': str, 'coach': int}, ...]
    confirmation_status: str  # "confirmed", "waitlist", "partial"
    message: str
    alternative_offerings: Optional[List[Dict]] = None


class SmartSeatAllocationEngine:
    """
    Intelligent seat allocation considering fairness, preferences,
    and business constraints.
    
    Algorithm:
    1. Load coach layouts and current availability
    2. Group passengers (family seating)
    3. Allocate main group slots
    4. Assign preferred berths
    5. Respect accessibility needs
    6. Enforce overbooking limits
    7. Generate PNR and confirmation
    """
    
    # Overbooking margins: Oversell capacity to account for cancellations
    OVERBOOKING_MARGIN_MIN = 0.05  # 5% oversell
    OVERBOOKING_MARGIN_MAX = 0.10  # 10% oversell
    
    # Seat preference scoring (higher = better match)
    PREFERENCE_SCORE_WEIGHTS = {
        'berth_type_match': 3.0,
        'accessibility': 2.0,
        'near_window': 1.0,
        'near_corridor': 0.5,
        'same_coach': 2.0,  # Keep family together
    }
    
    def __init__(self):
        """Initialize allocation engine."""
        self.coach_layouts: Dict[int, CoachLayout] = {}
        self.load_coach_configurations()
    
    def allocate_seats(self, request: AllocationRequest) -> AllocationResult:
        """
        Main allocation method.
        
        Allocate seats for passengers considering preferences and fairness.
        """
        # Validate request
        valid, error_msg = request.validate()
        if not valid:
            return AllocationResult(
                success=False,
                pnr_number=request.pnr_number,
                allocated_seats=[],
                allocations=[],
                confirmation_status="failed",
                message=error_msg
            )
        
        logger.info(
            f"Allocating {request.num_passengers} seats for PNR {request.pnr_number} "
            f"on trip {request.trip_id}"
        )
        
        try:
            # Step 1: Load current availability
            available_coaches = self._get_available_coaches(
                request.trip_id,
                request.travel_date
            )
            
            if not available_coaches:
                return AllocationResult(
                    success=False,
                    pnr_number=request.pnr_number,
                    allocated_seats=[],
                    allocations=[],
                    confirmation_status="waitlist",
                    message="No coaches available - added to waitlist"
                )
            
            # Step 2: Group passengers (families, couples, etc.)
            groups = self._group_passengers(request.passengers)
            
            # Step 3: Try to allocate groups
            allocations = []
            allocated_seats = []
            
            for group in groups:
                group_allocations = self._allocate_group(
                    group,
                    available_coaches,
                    request.allow_split
                )
                
                if group_allocations is None:
                    # Can't allocate this group
                    return AllocationResult(
                        success=False,
                        pnr_number=request.pnr_number,
                        allocated_seats=allocated_seats,
                        allocations=allocations,
                        confirmation_status="waitlist",
                        message=f"Cannot allocate {len(group)} seats - partial allocation offered"
                    )
                
                allocations.extend(group_allocations)
                allocated_seats.extend([a['seat'] for a in group_allocations])
            
            # Step 4: Build response
            result = AllocationResult(
                success=True,
                pnr_number=request.pnr_number,
                allocated_seats=allocated_seats,
                allocations=[
                    {
                        'passenger': a['passenger_name'],
                        'berth': a['seat'].berth_id,
                        'coach': a['seat'].coach_number,
                        'berth_type': a['seat'].berth_type.value
                    }
                    for a in allocations
                ],
                confirmation_status="confirmed",
                message=f"Successfully allocated {len(allocations)} seats"
            )
            
            logger.info(f"Allocation success: {result.message}")
            return result
        
        except Exception as e:
            logger.error(f"Allocation failed: {e}", exc_info=True)
            return AllocationResult(
                success=False,
                pnr_number=request.pnr_number,
                allocated_seats=[],
                allocations=[],
                confirmation_status="failed",
                message=f"Allocation error: {str(e)}"
            )
    
    def _get_available_coaches(
        self,
        trip_id: int,
        travel_date: str
    ) -> List[CoachLayout]:
        """
        Get list of coaches with current availability.
        
        In production, query from inventory service.
        For now, return mock data.
        """
        # Mock: Return 3 sample coaches
        coaches = []
        
        for coach_num in range(1, 4):
            coach_type = CoachType.SLEEPER if coach_num == 1 else CoachType.AC_THREE
            seats = self._generate_coach_seats(coach_type, coach_num)
            
            coach = CoachLayout(
                coach_number=coach_num,
                coach_type=coach_type,
                total_seats=72,  # Typical Indian rail coach
                lower_berths=12,
                upper_berths=12,
                side_lower_berths=12,
                side_upper_berths=12,
                accessible_seats=2,
                seats=seats
            )
            coaches.append(coach)
        
        return coaches
    
    def _generate_coach_seats(
        self,
        coach_type: CoachType,
        coach_number: int
    ) -> List[Seat]:
        """Generate berth list for a coach."""
        seats = []
        seat_num = 1
        
        # Lower berths
        for i in range(12):
            seats.append(Seat(
                berth_id=f"{coach_number:02d}-LB-{seat_num:02d}",
                coach_number=coach_number,
                berth_type=BerthType.LOWER,
                is_available=random.random() > 0.3,  # 70% available
                is_near_window=i % 2 == 0
            ))
            seat_num += 1
        
        # Upper berths
        for i in range(12):
            seats.append(Seat(
                berth_id=f"{coach_number:02d}-UB-{seat_num:02d}",
                coach_number=coach_number,
                berth_type=BerthType.UPPER,
                is_available=random.random() > 0.3,
                is_near_window=i % 2 == 0
            ))
            seat_num += 1
        
        # Side lower berths
        for i in range(12):
            seats.append(Seat(
                berth_id=f"{coach_number:02d}-SL-{seat_num:02d}",
                coach_number=coach_number,
                berth_type=BerthType.SIDE_LOWER,
                is_available=random.random() > 0.3,
                is_near_corridor=True
            ))
            seat_num += 1
        
        # Side upper berths
        for i in range(12):
            seats.append(Seat(
                berth_id=f"{coach_number:02d}-SU-{seat_num:02d}",
                coach_number=coach_number,
                berth_type=BerthType.SIDE_UPPER,
                is_available=random.random() > 0.3,
                is_near_corridor=True
            ))
            seat_num += 1
        
        return seats
    
    def _group_passengers(self, passengers: List[Dict]) -> List[List[Dict]]:
        """
        Group passengers for family seating.
        
        Try to keep groups of 2-3 together, allocate singles individually.
        """
        if len(passengers) <= 3:
            return [passengers]  # Single group
        
        # Simple grouping: pairs + remainder
        groups = []
        for i in range(0, len(passengers), 2):
            if i + 1 < len(passengers):
                groups.append(passengers[i:i+2])
            else:
                groups.append([passengers[i]])
        
        return groups
    
    def _allocate_group(
        self,
        group: List[Dict],
        coaches: List[CoachLayout],
        allow_split: bool = False
    ) -> Optional[List[Dict]]:
        """
        Allocate a group to berths.
        
        Returns list of allocations or None if impossible.
        """
        group_size = len(group)
        
        # Try to allocate within single coach first
        for coach in coaches:
            allocation = self._try_allocate_in_coach(group, coach)
            if allocation:
                return allocation
        
        # If allow_split, allocate across coaches
        if allow_split and group_size <= 3:
            allocations = []
            for passenger in group:
                # Find single seat in any coach
                for coach in coaches:
                    available = [s for s in coach.seats if s.is_available]
                    if available:
                        seat = self._select_best_seat(passenger, [available[0]])
                        allocations.append({
                            'passenger_name': passenger.get('name', 'Unknown'),
                            'seat': seat
                        })
                        seat.is_available = False
                        break
            
            if len(allocations) == group_size:
                return allocations
        
        return None
    
    def _try_allocate_in_coach(
        self,
        group: List[Dict],
        coach: CoachLayout
    ) -> Optional[List[Dict]]:
        """Try to allocate all group members in single coach."""
        # Get available seats in coach
        available = [s for s in coach.seats if s.is_available]
        
        if len(available) < len(group):
            return None  # Not enough space
        
        allocations = []
        
        for passenger in group:
            # Select best matching seat
            seat = self._select_best_seat(passenger, available)
            if seat is None:
                return None  # No suitable seat found
            
            allocations.append({
                'passenger_name': passenger.get('name', 'Unknown'),
                'seat': seat
            })
            
            available.remove(seat)
            seat.is_available = False
        
        return allocations
    
    def _select_best_seat(
        self,
        passenger: Dict,
        available_seats: List[Seat]
    ) -> Optional[Seat]:
        """
        Select best matching seat using preference scoring.
        """
        if not available_seats:
            return None
        
        preferences = passenger.get('berth_preference', BerthPreference())
        
        # Score each seat
        scores = []
        for seat in available_seats:
            score = self._score_seat_match(seat, preferences)
            scores.append((score, seat))
        
        # Return seat with highest score
        scores.sort(reverse=True)
        return scores[0][1]
    
    def _score_seat_match(
        self,
        seat: Seat,
        preferences: BerthPreference
    ) -> float:
        """Calculate preference match score for a seat."""
        score = 0.0
        
        # Berth type match
        if preferences.berth_type == seat.berth_type or \
           preferences.berth_type == BerthType.NO_PREFERENCE:
            score += self.PREFERENCE_SCORE_WEIGHTS['berth_type_match']
        
        # Accessibility
        if preferences.accessibility_required and seat.is_accessible:
            score += self.PREFERENCE_SCORE_WEIGHTS['accessibility']
        
        # Window preference
        if preferences.prefer_near_window and seat.is_near_window:
            score += self.PREFERENCE_SCORE_WEIGHTS['near_window']
        
        # Corridor preference
        if preferences.prefer_near_corridor and seat.is_near_corridor:
            score += self.PREFERENCE_SCORE_WEIGHTS['near_corridor']
        
        return score
    
    def load_coach_configurations(self):
        """Load coach type configurations."""
        # Placeholder: In production, load from database
        pass
    
    def check_overbooking_feasibility(
        self,
        trip_id: int,
        requested_seats: int
    ) -> Tuple[bool, float]:
        """
        Check if allocation is within overbooking margins.
        
        Returns: (is_feasible, current_occupancy_pct)
        """
        # Placeholder: In production, query inventory service
        # For now, assume 60% current occupancy
        current_occupancy = 0.60
        
        # Check against margin
        max_allowed_occupancy = 1.0 + self.OVERBOOKING_MARGIN_MAX
        
        return current_occupancy <= max_allowed_occupancy, current_occupancy


# Global instance
smart_allocation_engine = SmartSeatAllocationEngine()
