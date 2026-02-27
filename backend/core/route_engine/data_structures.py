from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Set

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
    departure_code: str = ""        # Added for RapidAPI/Verification
    arrival_code: str = ""          # Added for RapidAPI/Verification
    fare: float = 0.0               # allow deserialization when fare missing
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

    def to_dict(self) -> Dict[str, Any]:
        """Production serialization for API response."""
        return {
            "trip_id": self.trip_id,
            "train_number": self.train_number,
            "train_name": self.train_name,
            "from_station": self.departure_code,
            "to_station": self.arrival_code,
            "departure_time": self.departure_time.isoformat(),
            "arrival_time": self.arrival_time.isoformat(),
            "duration": self.duration_minutes,
            "distance": self.distance_km,
            "fare": self.fare
        }


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "station_id": self.station_id,
            "station_name": self.station_name,
            "arrival_time": self.arrival_time.isoformat() if self.arrival_time != datetime.min else None,
            "departure_time": self.departure_time.isoformat() if self.departure_time != datetime.max else None,
            "wait_minutes": self.duration_minutes
        }


@dataclass
class Route:
    """Complete multi-transfer route"""
    segments: List[RouteSegment] = field(default_factory=list)
    transfers: List[TransferConnection] = field(default_factory=list)
    total_duration: int = 0
    total_cost: float = 0.0
    total_distance: float = 0.0
    raw_segment_cost: float = 0.0
    score: float = 0.0
    ml_score: float = 0.0
    reliability: float = 1.0
    availability_probability: float = 1.0 # Phase 8: P(booking success)
    is_locked: bool = True  # Added for booking intelligence unlock flow
    cost_diagnostics: Dict[str, float] = field(default_factory=dict)
    visited_stations: Set[int] = field(default_factory=set) # Optimization for RAPTOR cycle detection

    def to_dict(self) -> Dict[str, Any]:
        """Production serialization matching the blueprint."""
        return {
            "route_id": f"rt_{self.segments[0].trip_id}_{int(self.segments[0].departure_time.timestamp())}" if self.segments else "unknown",
            "segments": [s.to_dict() for s in self.segments],
            "transfers": [t.to_dict() for t in self.transfers],
            "total_duration": self.total_duration,
            "total_fare": self.total_cost,
            "total_distance": self.total_distance,
            "reliability": self.reliability,
            "score": self.score,
            "is_locked": self.is_locked,
            "availability_prob": self.availability_probability
        }

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
        self.total_distance += segment.distance_km
        self.raw_segment_cost += segment.fare
        # Use literal database cost without normalization
        self.total_cost = self.raw_segment_cost
        self.cost_diagnostics["legacy_segment_cost"] = self.raw_segment_cost

    def recompute_total_cost(self, multiplier: float):
        """Recompute the displayed fare. Now strictly uses raw segment cost as per user mandate."""
        # multiplier ignored - we use the cost given in tables
        self.total_cost = round(self.raw_segment_cost, 2)
        self.cost_diagnostics["normalized_cost"] = self.total_cost

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
class UserContext:
    """User preferences and context for personalization"""
    user_id: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    loyalty_tier: str = "standard"
    past_bookings: List[Dict] = field(default_factory=list)
