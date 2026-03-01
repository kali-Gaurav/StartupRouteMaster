from pydantic import BaseModel, Field
from typing import Optional, List

class UnifiedSearchRequest(BaseModel):
    source: str = Field(..., min_length=2)
    destination: str = Field(..., min_length=2)
    date: str
    passengers: int = 1
    preferences: Optional[str] = Field(
        "balanced",
        description="fastest | cheapest | safest | balanced"
    )
    multi_modal: bool = True
    max_results: int = 10

class JourneySegment(BaseModel):
    mode: str
    from_station: str
    to_station: str
    departure: str
    arrival: str
    duration_minutes: int
    price: float
    train_number: Optional[str] = None
    train_name: Optional[str] = None

class JourneyOption(BaseModel):
    journey_id: str
    total_price: float
    total_duration: int
    safety_score: float
    segments: List[JourneySegment]
    is_locked: bool = True # Revenue model: details hidden until payment

class UnifiedSearchResponse(BaseModel):
    status: str = "success"
    options: List[JourneyOption]
    latency_ms: float
