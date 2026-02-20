"""
Shared Data Structures - Consolidated across all engines

This module consolidates all dataclasses and configuration objects used across:
- routing/engine.py (RailwayRouteEngine)
- inventory/seat_allocator.py (AdvancedSeatAllocationEngine)
- pricing/engine.py (DynamicPricingEngine)
- cache/manager.py (MultiLayerCache)

By centralizing these structures, we:
1. Eliminate code duplication (~100 lines)
2. Ensure consistency across engines
3. Make it easier to change data formats
4. Enable better type checking
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Dict, List, Optional, Set, Any
from enum import Enum


# ==============================================================================
# QUERY & INPUT STRUCTURES
# ==============================================================================

@dataclass
class RouteQuery:
    """Route query parameters for caching and search."""
    from_station: str
    to_station: str
    date: date
    class_preference: Optional[str] = None
    max_transfers: int = 3
    include_wait_time: bool = True

    def cache_key(self) -> str:
        """Generate cache key for route query"""
        import hashlib
        key_data = f"{self.from_station}:{self.to_station}:{self.date.isoformat()}"
        if self.class_preference:
            key_data += f":{self.class_preference}"
        key_data += f":{self.max_transfers}:{self.include_wait_time}"
        return f"route:{hashlib.md5(key_data.encode()).hexdigest()[:16]}"

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class AvailabilityQuery:
    """Availability query parameters for caching."""
    train_id: int
    from_stop_id: int
    to_stop_id: int
    travel_date: date
    quota_type: str  # 'tatkal', 'general', 'premium', etc.
    passengers: int = 1

    def cache_key(self) -> str:
        """Generate cache key for availability query"""
        import hashlib
        key_data = f"{self.train_id}:{self.from_stop_id}:{self.to_stop_id}:{self.travel_date.isoformat()}:{self.quota_type}"
        return f"availability:{hashlib.md5(key_data.encode()).hexdigest()[:16]}"

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class PassengerPreference:
    """Passenger seat and booking preferences."""
    berth_type: Optional[str] = None  # 'LB', 'UB', 'SL', 'CP', etc.
    window_preference: Optional[bool] = None  # True=window, False=aisle, None=any
    is_female: bool = False
    is_senior: bool = False
    is_disabled: bool = False
    is_child: bool = False
    group_with: List[str] = field(default_factory=list)  # PNRs to group with

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class PricingContext:
    """Context for dynamic pricing decision."""
    base_cost: float
    demand_score: float  # 0 to 1
    occupancy_rate: float  # Current occupancy 0 to 1
    time_to_departure_hours: float
    route_popularity: float  # 0 to 1
    user_booking_history: Optional[Dict] = None
    is_peak_season: bool = False
    is_holiday: bool = False
    competitor_price: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


# ==============================================================================
# RESULT & OUTPUT STRUCTURES
# ==============================================================================

@dataclass
class SeatAllocationResult:
    """Result of seat allocation request."""
    success: bool
    pnr: str
    seats: List[str] = field(default_factory=list)
    coach: str = ""
    berth_type: str = ""
    status: str = "pending"  # confirmed, waitlist, rac
    total_amount: float = 0.0
    message: str = ""
    alternatives: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class DynamicPricingResult:
    """Result of dynamic pricing calculation."""
    base_cost: float
    dynamic_multiplier: float
    final_price: float
    tax_amount: float
    convenience_fee: float
    total_price: float
    pricing_factors: Dict[str, float]
    explanation: str
    recommendation: str  # "buy_now", "wait", "premium"

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        result_dict = asdict(self)
        return result_dict


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def request_count(self) -> int:
        """Total requests served."""
        return self.hits + self.misses

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            **asdict(self),
            'hit_rate': self.hit_rate,
            'request_count': self.request_count
        }

    def reset(self):
        """Reset all metrics."""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0


# ==============================================================================
# CONFIGURATION & CONTEXT STRUCTURES
# ==============================================================================

@dataclass
class Coach:
    """Coach information and seat status."""
    coach_id: str
    coach_class: str  # SL, AC3, AC2, AC1, etc.
    total_seats: int
    seats: Dict[str, str] = field(default_factory=dict)  # seat_num -> status

    def available_count(self) -> int:
        """Count available seats."""
        return sum(1 for s in self.seats.values() if s == "available")

    def occupancy_rate(self) -> float:
        """Get occupancy rate (0.0 to 1.0)."""
        total = max(len(self.seats), 1)
        booked = sum(1 for s in self.seats.values() if s in ["booked", "reserved"])
        return booked / total

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'coach_id': self.coach_id,
            'coach_class': self.coach_class,
            'total_seats': self.total_seats,
            'available_seats': self.available_count(),
            'occupancy_rate': self.occupancy_rate(),
        }


@dataclass
class TraceContext:
    """Unified context for distributed tracing."""
    request_id: str
    stage: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_metric(self, key: str, value: Any):
        """Add a metric to trace context."""
        self.metrics[key] = value

    def add_error(self, error: str):
        """Record an error."""
        self.errors.append(error)

    def add_warning(self, warning: str):
        """Record a warning."""
        self.warnings.append(warning)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'request_id': self.request_id,
            'stage': self.stage,
            'timestamp': self.timestamp.isoformat(),
            'duration_ms': self.duration_ms,
            'metrics': self.metrics,
            'explanation': self.explanation,
            'errors': self.errors,
            'warnings': self.warnings,
        }


# ==============================================================================
# VALIDATION & STATUS ENUMS
# ==============================================================================

class BerthType(Enum):
    """Berth types in Indian trains."""
    LOWER = "LB"
    UPPER = "UB"
    SIDE_LOWER = "SL"
    SIDE_UPPER = "SU"
    COUPE = "CP"
    NO_PREFERENCE = "NO_PREF"


class SeatStatus(Enum):
    """Seat availability status."""
    AVAILABLE = "available"
    BOOKED = "booked"
    RESERVED = "reserved"  # For maintenance/staff
    BLOCKED = "blocked"    # Safety/accessibility reason


class AllocationStatus(Enum):
    """Seat allocation status."""
    CONFIRMED = "confirmed"
    WAITLIST = "waitlist"
    RAC = "rac"  # Reservation Against Cancellation
    OVERBOOKED = "confirmed_overbooked"
    PENDING = "pending"


class EngineMode(Enum):
    """Operating mode for engines."""
    OFFLINE = "offline"      # No live APIs
    HYBRID = "hybrid"        # Some live APIs
    ONLINE = "online"        # All live APIs available


class QuotaType(Enum):
    """Railway quota types."""
    GENERAL = "general"
    TATKAL = "tatkal"
    PREMIUM = "premium"
    SENIOR_CITIZEN = "senior_citizen"
    LADIES = "ladies"
    PERSON_WITH_DISABILITY = "pwd"


# ==============================================================================
# LEGACY FIELD CONVERSION UTILITIES
# ==============================================================================

def seat_status_from_string(status: str) -> str:
    """Convert string to seat status."""
    status_lower = status.lower()
    for status_enum in SeatStatus:
        if status_enum.value == status_lower:
            return status_enum.value
    return SeatStatus.AVAILABLE.value


def berth_type_from_string(berth: str) -> str:
    """Convert string to berth type."""
    berth_upper = berth.upper()
    for berth_enum in BerthType:
        if berth_enum.value == berth_upper:
            return berth_enum.value
    return BerthType.NO_PREFERENCE.value


# ==============================================================================
# FACTORY FUNCTIONS FOR COMMON SCENARIOS
# ==============================================================================

def create_default_passenger_preference() -> PassengerPreference:
    """Create a passenger with no specific preferences."""
    return PassengerPreference()


def create_accessible_preference() -> PassengerPreference:
    """Create accessibility-focused preference."""
    return PassengerPreference(
        berth_type=BerthType.LOWER.value,
        is_disabled=True
    )


def create_family_preference(age: int) -> PassengerPreference:
    """Create family member preference based on age."""
    return PassengerPreference(
        is_child=age < 18,
        is_senior=age > 60,
        group_with=[]
    )
