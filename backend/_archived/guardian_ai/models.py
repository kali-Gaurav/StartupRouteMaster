from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class MissionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"

class LocationMetadata(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    last_known_station: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class JourneyDetails(BaseModel):
    pnr: Optional[str] = None
    train_number: Optional[str] = None
    source_station: str
    destination_station: str
    departure_time: datetime
    arrival_time: datetime

class SafetyEvent(BaseModel):
    event_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    category: str
    description: str
    risk_delta: float
    resolved: bool = False

class Mission(BaseModel):
    mission_id: str
    user_id: str
    status: MissionStatus = MissionStatus.ACTIVE
    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0  # 0.0 to 100.0
    
    journey: JourneyDetails
    location: LocationMetadata = Field(default_factory=LocationMetadata)
    
    events: List[SafetyEvent] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
