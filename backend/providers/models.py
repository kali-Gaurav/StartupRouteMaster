"""
Unified Pydantic models for data returned by the Provider Gateway and related services.

These models ensure that no matter which data source is used, the rest of the
application receives a consistent, validated data structure.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

# --- Existing models ---
class UnifiedLiveStatus(BaseModel):
    train_number: str
    current_station_code: Optional[str] = None
    current_station_name: Optional[str] = None
    status_as_of: datetime = Field(default_factory=datetime.utcnow)
    delay_minutes: int = 0
    running_status: str = Field(..., description="e.g., 'On Time', 'Delayed', 'Cancelled'")
    data_source: str = Field(..., description="Identifier for the origin of the data, e.g., 'rapidapi', 'ntes_scraper', 'external_redirect'")
    confidence_score: float = Field(default=1.0, description="A score from 0.0 to 1.0 indicating data reliability")
    external_url: Optional[str] = None
    is_external: bool = False

class UnifiedStation(BaseModel):
    sequence: int
    station_code: str
    station_name: str
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    distance_km: float

class UnifiedAvailability(BaseModel):
    train_number: str
    travel_date: str
    from_station_code: str
    to_station_code: str
    class_code: Optional[str] = None
    quota: str = "GN"
    availability_status: str # e.g., "AVAILABLE-005", "WL-002"
    fare: Optional[float] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    data_source: str
    confidence_score: float = 1.0

class UnifiedSchedule(BaseModel):
    train_number: str
    train_name: str
    schedule: List[UnifiedStation]
    data_source: str
    confidence_score: float = 1.0

# --- Models for Fare and PNR Status ---
class UnifiedFareInfo(BaseModel):
    class_code: str
    quota: str
    fare: float
    available_seats: int
    wl_count: Optional[int] = None # Waitlist count
    rac_seats: Optional[int] = None

class UnifiedFare(BaseModel):
    train_number: str
    from_station_code: str
    to_station_code: str
    travel_date: str
    fare_details: List[UnifiedFareInfo] # List of fares for different classes/quotas
    data_source: str
    confidence_score: float = 1.0

class UnifiedPNRStatus(BaseModel):
    pnr_number: str
    train_number: str
    train_name: str
    from_station_code: str
    to_station_code: str
    travel_date: str
    booking_status: str # e.g., "CNF", "W/L", "RAC"
    current_station_code: Optional[str] = None
    current_station_name: Optional[str] = None
    reservation_status: str # e.g., "Confirmed", "Waitlisted"
    chart_prepared: bool = False
    data_source: str
    confidence_score: float = 1.0

# --- New models for Service Request/Response ---

class BookingVerificationRequest(BaseModel):
    """Request model for booking verification."""
    pnr_number: Optional[str] = None
    train_number: Optional[str] = None
    travel_date: Optional[str] = None # Expecting 'YYYY-MM-DD' string
    from_station_code: Optional[str] = None
    to_station_code: Optional[str] = None
    class_code: Optional[str] = None
    quota: Optional[str] = "GN"
    booking_fare: Optional[float] = None

class BookingVerificationResponse(BaseModel):
    """Response model for booking verification results."""
    pnr_status: Optional[Dict[str, Any]] = None # PNR data can be complex, using Dict for now
    live_status: Optional[UnifiedLiveStatus] = None
    fare_details: Optional[List[Dict[str, Any]]] = None # List of fare dicts, mirroring original service
    overall_verification: str = "Unknown" # e.g., "Success", "Warning", "Failed"
    issues: List[str] = Field(default_factory=list) # List of detected issues

# --- New model for Booking Data Storage (for monitoring/alerting) ---

class BookingMonitorRecord(BaseModel):
    """
    Represents a booking record that needs to be monitored for status changes.
    Stores essential booking info and the last known status fetched by the gateway.
    """
    booking_id: str # Unique identifier for the booking itself
    user_id: str
    pnr_number: Optional[str] = None
    train_number: Optional[str] = None
    travel_date: Optional[str] = None # 'YYYY-MM-DD'
    from_station_code: Optional[str] = None
    to_station_code: Optional[str] = None
    class_code: Optional[str] = None
    quota: Optional[str] = "GN"
    booking_fare: Optional[float] = None
    
    # Last known status from gateway for change detection
    last_known_live_status: Optional[Dict[str, Any]] = None # Store as dict to be JSON serializable
    last_known_pnr_status: Optional[Dict[str, Any]] = None
    last_known_fare_details: Optional[List[Dict[str, Any]]] = None
    
    # Monitoring control flags
    is_monitoring_active: bool = True
    last_check_timestamp: Optional[datetime] = None
    alert_preferences: Dict[str, Any] = Field(default_factory=dict) # e.g., {"delay_threshold_minutes": 60, "notify_on_cancellation": true}

class AlertMessage(BaseModel):
    """
    Structured alert message for the queuing system.
    """
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    booking_id: str
    alert_type: str # "delay", "cancellation", "pnr_update", etc.
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = Field(default_factory=dict)
    priority: str = "normal"
