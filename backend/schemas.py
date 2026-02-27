from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    phone_number: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserRead(UserBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# --- Review Schemas ---
class ReviewBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class ReviewCreate(ReviewBase):
    booking_id: str


class ReviewRead(ReviewBase):
    id: str
    user_id: str
    booking_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class RouteSegmentSchema(BaseModel):
    mode: str
    from_: str = Field(..., alias="from")
    to: str
    duration: str
    cost: float
    details: str

    class Config:
        populate_by_name = True


class SearchRequestSchema(BaseModel):
    source: str = Field(..., min_length=2, max_length=100)  # Relaxed pattern (fuzzy matching handles typos)
    destination: str = Field(..., min_length=2, max_length=100)
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}(T|\s)?.*$")
    budget: str = Field("all", pattern="^(all|economy|standard|premium)$")
    multi_modal: bool = Field(True, description="Whether to include multi-modal planning suggestions")
    women_safety_mode: bool = Field(False, description="Prioritize safer routes and avoid night layovers")

    # New fields for advanced features
    journey_type: Optional[str] = Field(None, pattern="^(single|connecting|circular|multi_city)$")
    return_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    cities: Optional[List[str]] = Field(None, description="List of cities for multi-city booking (max 3)")
    passenger_type: Optional[str] = Field("adult", pattern="^(adult|child|senior|student)$")
    concessions: Optional[List[str]] = Field(None, description="List of concessions")

    class Config:
        json_schema_extra = {
            "example": {
                "source": "Mumbai Central",
                "destination": "New Delhi",
                "date": "2025-12-25",
                "budget": "economy",
                "multi_modal": True,
                "journey_type": "single",
                "passenger_type": "adult",
                "concessions": []
            }
        }

# backward-compatibility alias used by legacy integrated_search module
SearchRequest = SearchRequestSchema


# NEW: Passenger Details Schema
class PassengerDetailsSchema(BaseModel):
    """Schema for passenger information in a booking."""
    full_name: str = Field(..., min_length=1, max_length=255)
    age: int = Field(..., ge=0, le=150)
    gender: str = Field(..., pattern="^(M|F|O|U)$") # Male, Female, Other, Unknown
    
    class Config:
        from_attributes = True

class BookingCreateSchema(BaseModel):
    route_id: str
    travel_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    booking_details: Dict[str, Any]
    amount_paid: float = Field(..., ge=0)
    passenger_details: Optional[List[PassengerDetailsSchema]] = None


class LocationUpdateSchema(BaseModel):
    latitude: float
    longitude: float
    speed: Optional[float] = None


# --- Availability Schemas ---------------------------------------------------
class AvailabilityCheckRequestSchema(BaseModel):
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    travel_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    quota_type: str
    passengers: int = Field(1, ge=1, le=6)

class AvailabilityCheckResponseSchema(BaseModel):
    available: bool
    available_seats: int
    total_seats: int
    waitlist_position: Optional[int] = None
    confirmation_probability: Optional[float] = None
    message: str
    # compatibility / extra fields used by frontend
    availability_status: Optional[str] = None
    fare: Optional[float] = None
    quota: Optional[str] = None
    class_type: Optional[str] = Field(None, alias="class")
    probability: Optional[float] = None

    class Config:
        populate_by_name = True

class BookingResponseSchema(BaseModel):
    id: str
    pnr_number: str
    user_id: str
    # travel_date stored as a date in the DB; allow either date or datetime
    travel_date: Optional[datetime]  # will accept date as well because of from_attributes
    booking_status: str
    amount_paid: float
    booking_details: Dict[str, Any]
    passenger_details: Optional[List[PassengerDetailsSchema]] = None
    created_at: datetime

    # deprecated fields that might appear
    payment_status: Optional[str] = None

    class Config:
        from_attributes = True
        extra = "ignore"  # ignore any other attributes coming from ORM
    # legacy passenger fields (kept for backward compatibility, usually the first passenger)
    gender: str = Field(..., pattern="^[MFO]$")  # M, F, O (Other)
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    document_type: Optional[str] = None  # Aadhar, PAN, Passport
    document_number: Optional[str] = None
    concession_type: Optional[str] = None
    concession_discount: float = Field(0.0, ge=0.0, le=100.0)
    meal_preference: Optional[str] = None  # Veg, NonVeg, Jain


# New schema for paginated booking responses
class BookingListSchema(BaseModel):
    bookings: List[BookingResponseSchema]
    total: int
    skip: int
    limit: int

    class Config:
        schema_extra = {
            "example": {
                "bookings": [],
                "total": 0,
                "skip": 0,
                "limit": 20
            }
        }

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "John Doe",
                "age": 35,
                "gender": "M",
                "phone_number": "+919876543210",
                "email": "john@example.com",
                "document_type": "Aadhar",
                "document_number": "1234-5678-9012",
                "concession_type": None,
                "meal_preference": "Veg"
            }
        }


# NEW: Booking Creation Schema
class BookingCreateSchema(BaseModel):
    """Schema for creating a new booking."""
    route_id: str
    travel_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    booking_details: dict  # Segments and route info
    amount_paid: float = Field(..., ge=0)
    passenger_details: Optional[List[PassengerDetailsSchema]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "route_id": "route_123",
                "travel_date": "2025-12-25",
                "booking_details": {"segments": []},
                "amount_paid": 5000.0,
                "passenger_details": [
                    {
                        "full_name": "John Doe",
                        "age": 35,
                        "gender": "M",
                        "phone_number": "+919876543210"
                    }
                ]
            }
        }


# NEW: Booking Status Response
class BookingStatusSchema(BaseModel):
    """Schema for booking status information."""
    pnr_number: str
    booking_status: str  # pending, confirmed, waiting_list, cancelled
    travel_date: str
    amount_paid: float
    created_at: datetime
    updated_at: Optional[datetime]
    passenger_count: int

    class Config:
        from_attributes = True


class RouteSummarySchema(BaseModel):
    id: str
    source: str
    destination: str
    total_duration: str
    total_cost: float
    budget_category: str
    num_transfers: int

    class Config:
        from_attributes = True


class RouteDetailSchema(BaseModel):
    id: str
    source: str
    destination: str
    segments: List[RouteSegmentSchema]
    total_duration: str
    total_cost: float
    budget_category: str
    num_transfers: int
    created_at: datetime
    is_unlocked: bool = False # Added for real-time unlock status

    class Config:
        from_attributes = True


class PaymentOrderSchema(BaseModel):
    route_id: str
    travel_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    is_unlock_payment: Optional[bool] = False
    # Optional route details for verification (if provided, speeds up verification)
    train_number: Optional[str] = None
    from_station_code: Optional[str] = None
    to_station_code: Optional[str] = None
    source_station_name: Optional[str] = None
    destination_station_name: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "route_id": "550e8400-e29b-41d4-a716-446655440000",
                "travel_date": "2025-12-25",
                "is_unlock_payment": False,
                "train_number": "12951",
                "from_station_code": "NDLS",
                "to_station_code": "MMCT"
            }
        }


class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str


class PaymentWebhookSchema(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str



class AdminBookingSchema(BaseModel):
    id: str
    user_name: str
    user_email: str
    user_phone: str
    route_id: str
    travel_date: str
    payment_id: Optional[str]
    payment_status: str
    amount_paid: float
    booking_details: dict
    created_at: datetime

    class Config:
        from_attributes = True


# --- Integrated Search Schemas ---

class PassengerInfo(BaseModel):
    """Passenger information for search and booking."""
    full_name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=0, le=150)
    gender: str = Field(..., pattern="^[MFO]$")
    concession_type: Optional[str] = None
    phone: Optional[str] = None


class JourneyInfoResponse(BaseModel):
    """Complete journey info for display"""
    journey_id: str
    num_segments: int
    distance_km: float
    travel_time: str
    num_transfers: int
    is_direct: bool
    cheapest_fare: float
    premium_fare: float
    has_overnight: bool
    availability_status: str


class RouteGraphNode(BaseModel):
    segment_id: str
    train_number: str
    train_name: Optional[str]
    from_station_code: str
    to_station_code: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    distance_km: float
    coach_preference: str
    verification_source: Optional[str] = None
    availability_status: str = "UNKNOWN"

class RouteGraphEdge(BaseModel):
    from_segment_id: str
    to_segment_id: str
    transfer_station_code: str
    wait_minutes: int
    platform: Optional[str] = None
    transfer_reason: str = "interchange"

class VerificationSummary(BaseModel):
    rapidapi_calls: int
    seat_availability: Dict[str, Dict]
    fare_verification: Dict[str, Dict]
    warnings: List[str]

class DetailedJourneyResponse(BaseModel):
    """Complete detailed journey with all calculations"""
    journey: JourneyInfoResponse
    segments: List[Dict]
    seat_allocation: Dict
    verification: Dict
    fare_breakdown: Dict
    can_unlock_details: bool
    # new fields for visualization and transparency
    route_graph: Optional[Dict[str, Any]] = None
    verification_summary: Optional[VerificationSummary] = None


class BookingConfirmationRequest(BaseModel):
    """Request to confirm a booking"""
    journey_id: str
    selected_coach: str
    passengers: List[PassengerInfo]
    payment_method: str = "online"


class HealthCheckResponse(BaseModel):
    status: str
    database: str
    cache: str
    timestamp: datetime


class SearchRoutesResponseSchema(BaseModel):
    routes: List[RouteSummarySchema]
    message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "routes": [
                    {
                        "id": "route_123",
                        "source": "Mumbai",
                        "destination": "Goa",
                        "total_duration": "8h 30m",
                        "total_cost": 1200.0
                    }
                ],
                "message": "Search completed successfully"
            }
        }


# ==============================================================================
# BOOKING QUEUE SYSTEM SCHEMAS
# ==============================================================================

class BookingRequestPassengerSchema(BaseModel):
    """Passenger details for booking request."""
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)
    gender: str = Field(..., pattern="^(M|F|O)$")
    berth_preference: Optional[str] = Field(None, pattern="^(LOWER|MIDDLE|UPPER|SIDE_LOWER|SIDE_UPPER)$")
    id_proof_type: Optional[str] = Field(None, pattern="^(AADHAR|PAN|PASSPORT)$")
    id_proof_number: Optional[str] = Field(None, max_length=50)

    class Config:
        from_attributes = True


class BookingRequestCreateSchema(BaseModel):
    """Schema for creating a booking request."""
    source_station: str = Field(..., min_length=2, max_length=20)
    destination_station: str = Field(..., min_length=2, max_length=20)
    journey_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    train_number: str = Field(..., min_length=1, max_length=20)
    train_name: Optional[str] = Field(None, max_length=100)
    class_type: str = Field("AC_THREE_TIER", pattern="^(SL|AC3|AC2|AC1|CC|EC)$")
    quota: str = Field("GENERAL", pattern="^(GENERAL|TATKAL|LADIES|SENIOR_CITIZEN|DEFENCE|FOREIGN_TOURIST)$")
    route_details: Optional[Dict[str, Any]] = None  # Full route segments JSON
    passengers: List[BookingRequestPassengerSchema] = Field(..., min_items=1, max_items=6)

    class Config:
        json_schema_extra = {
            "example": {
                "source_station": "NDLS",
                "destination_station": "MMCT",
                "journey_date": "2026-03-15",
                "train_number": "12951",
                "train_name": "Rajdhani Express",
                "class_type": "AC3",
                "quota": "GENERAL",
                "passengers": [
                    {
                        "name": "John Doe",
                        "age": 35,
                        "gender": "M",
                        "berth_preference": "LOWER"
                    }
                ]
            }
        }


class BookingRequestResponseSchema(BaseModel):
    """Response schema for booking request."""
    id: str
    user_id: str
    source_station: str
    destination_station: str
    journey_date: str
    train_number: str
    train_name: Optional[str]
    class_type: str
    quota: str
    status: str
    verification_status: str
    payment_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    queue_status: Optional[str] = None  # From BookingQueue if exists

    class Config:
        from_attributes = True


class BookingQueueResponseSchema(BaseModel):
    """Response schema for booking queue entry."""
    id: str
    booking_request_id: str
    priority: int
    execution_mode: str
    status: str
    scheduled_time: Optional[datetime]
    created_at: datetime
    booking_request: Optional[BookingRequestResponseSchema] = None

    class Config:
        from_attributes = True


class BookingResultResponseSchema(BaseModel):
    """Response schema for booking result."""
    id: str
    booking_request_id: str
    pnr_number: Optional[str]
    ticket_status: Optional[str]
    coach_details: Optional[Dict[str, Any]]
    seat_details: Optional[Dict[str, Any]]
    execution_method: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RefundRequestSchema(BaseModel):
    """Schema for requesting a refund."""
    booking_request_id: str
    reason: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "booking_request_id": "req_123",
                "reason": "Booking failed - seats unavailable"
            }
        }


class RefundResponseSchema(BaseModel):
    """Response schema for refund."""
    id: str
    booking_request_id: str
    amount: float
    currency: str
    reason: Optional[str]
    status: str
    razorpay_refund_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
