"""
Shared journey segment data structures - UNIFIED VERSION
"""
from dataclasses import dataclass, asdict
from typing import Dict, List

@dataclass
class SegmentDetail:
    """Complete details for one leg of a journey"""
    segment_id: str
    train_number: str
    train_name: str
    depart_station: str
    depart_code: str
    depart_time: str
    depart_platform: str
    
    arrival_station: str
    arrival_code: str
    arrival_time: str
    arrival_platform: str
    
    distance_km: float
    travel_time_hours: float
    travel_time_mins: int
    
    running_days: str
    halt_times: Dict[str, int]
    
    ac_first_available: int
    ac_second_available: int
    ac_third_available: int
    sleeper_available: int
    
    base_fare: float
    tatkal_applicable: bool

    def to_dict(self):
        return asdict(self)

@dataclass
class JourneyOption:
    """Complete journey with multiple segments"""
    journey_id: str
    segments: List[SegmentDetail]
    start_date: str
    end_date: str
    
    total_distance_km: float
    total_travel_time_mins: int
    num_segments: int
    num_transfers: int
    
    cheapest_fare: float
    premium_fare: float
    
    is_direct: bool
    has_overnight: bool
    
    availability_status: str

    def to_dict(self):
        return {**asdict(self), "segments": [s.to_dict() for s in self.segments]}
