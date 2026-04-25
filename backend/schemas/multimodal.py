from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class TransportMode(str, Enum):
    TRAIN = "TRAIN"
    FLIGHT = "FLIGHT"
    BUS = "BUS"
    TAXI = "TAXI"
    WALK = "WALK"

class MultimodalSegment(BaseModel):
    """
    [Titan:Omniscient] Unified segment for all transport modes.
    Ensures that an API flight and a DB train can be compared 1:1.
    """
    mode: TransportMode
    provider: str  # e.g., "Indigo", "RedBus", "Uber", "IRCTC"
    
    source_code: str
    source_name: str
    destination_code: str
    destination_name: str
    
    departure_time: datetime
    arrival_time: datetime
    
    duration_minutes: int
    price: float
    currency: str = "INR"
    
    # Metadata for specific modes
    # Flight: Flight number, gate, terminal
    # Bus: Bus type (Ac/Non-Ac), deck
    # Taxi: Car type, estimated wait
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Scoring attributes
    safety_score: float = 1.0
    comfort_score: float = 1.0
    reliability_score: float = 1.0

class FlightInventory(BaseModel):
    flight_no: str
    airline: str
    stops: int
    cabin_class: str
    is_refundable: bool = True

class BusInventory(BaseModel):
    operator: str
    bus_type: str
    amenities: List[str] = []

class MultimodalResponse(BaseModel):
    query_id: str
    segments: List[MultimodalSegment]
    provider_status: str # "HEALTHY", "DEGRADED", "ERROR"
    latency_ms: int
