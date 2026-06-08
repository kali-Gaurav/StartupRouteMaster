
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from .common import Persona

class RouteSegment(BaseModel):
    trip_id: Any
    from_station: str
    to_station: str
    departure_time: datetime
    arrival_time: datetime
    duration: int
    distance: float
    fare: float = 0.0
    train_name: str = ""
    train_number: str = ""
    has_pantry: bool = False
    departure_platform: Optional[str] = None
    arrival_platform: Optional[str] = None
    departure_stop_id: int
    arrival_stop_id: int
    metadata: Dict[str, Any] = {}

class TransferConnection(BaseModel):
    station_id: int
    station_name: str
    arrival_time: Optional[datetime] = None
    departure_time: Optional[datetime] = None
    wait_minutes: int

class Route(BaseModel):
    route_id: str
    journey_id: str
    segments: List[RouteSegment]
    legs: List[RouteSegment] # Alias for segments to match API v2 expectations
    transfers: List[TransferConnection]
    total_duration: int
    total_fare: float
    total_distance: float
    reliability: float = 1.0
    score: float = 0.0
    is_locked: bool = True
    is_featured: bool = False
    highlight_label: Optional[str] = None
    availability_prob: float = 1.0
    metadata: Dict[str, Any] = {}

class RouteConstraints(BaseModel):
    max_journey_time: int = 3600
    max_transfers: int = 3
    min_transfer_time: int = 15
    max_layover_time: int = 480
    persona: Persona = Persona.COMFORT
    quota: str = "GN"
    max_results: int = 15
    cursor: Optional[float] = None
