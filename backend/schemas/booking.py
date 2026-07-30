"""
Booking Schemas - Pydantic models for booking API.
"""

from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, EmailStr


class BookingStatus(str, Enum):
    """Booking status values."""
    INITIATED = "initiated"
    VALIDATING = "validating"
    SEAT_ALLOCATING = "seat_allocating"
    PRICING = "pricing"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_PROCESSING = "payment_processing"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    WAITLIST = "waitlist"


class PassengerDetails(BaseModel):
    """Passenger information for booking."""
    full_name: str = Field(..., min_length=2, max_length=255)
    age: int = Field(..., ge=1, le=150)
    gender: str = Field(..., pattern="^(M|F|O)$")
    phone_number: Optional[str] = Field(None, pattern="^[0-9]{10,15}$")
    email: Optional[EmailStr] = None
    berth_preference: Optional[str] = Field(None, pattern="^(lower|middle|upper|side_lower|side_upper|window|aisle)$")
    meal_preference: Optional[str] = None
    concession_type: Optional[str] = None


class BookingRequest(BaseModel):
    """Request to create a booking."""
    journey_id: str = Field(..., description="Selected journey ID from search")
    train_number: str = Field(..., description="Train number")
    from_station: str = Field(..., description="Origin station code")
    to_station: str = Field(..., description="Destination station code")
    travel_date: str = Field(..., pattern="^[0-9]{4}-[0-9]{2}-[0-9]{2}$", description="Travel date (YYYY-MM-DD)")
    passengers: List[PassengerDetails] = Field(..., min_length=1, max_length=6)
    class_type: str = Field(..., pattern="^(SL|3A|2A|1A|CC|2S|EC)$", description="Class type")
    berth_preference: Optional[str] = Field(None, pattern="^(lower|middle|upper|side_lower|side_upper)$")
    meal_preference: Optional[str] = None
    payment_method: str = Field(..., pattern="^(upi|card|net_banking)$")
    webhook_url: Optional[str] = None


class IRCTCLinkRequest(BaseModel):
    """Request to generate an IRCTC deep link."""
    from_code: str
    to_code: str
    date: str # YYYY-MM-DD


class IRCTCLinkResponse(BaseModel):
    """Response containing the IRCTC deep link."""
    url: str


class SavePNRRequest(BaseModel):
    """Request to save a PNR for a segment."""
    journey_id: str
    segment_index: int
    pnr: str
    train_number: str


class SegmentPNRResponse(BaseModel):
    """Response after saving a PNR."""
    status: str = "success"
    message: str


class BookingResponse(BaseModel):
    """Booking response."""
    booking_id: str
    pnr_number: str
    status: BookingStatus
    total_amount: float
    payment_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    seats_allocated: List[str] = []
    waitlist_position: Optional[int] = None
    
    class Config:
        from_attributes = True

# Aliases for different API versions
BookingResponseSchema = BookingResponse

class SubmitUtrSchema(BaseModel):
    """Schema for submitting UTR (Unified Transaction Reference) for payment verification."""
    booking_id: str
    utr_number: str = Field(..., min_length=10, max_length=50)
    payment_method: str = "upi"


class BookingListResponse(BaseModel):
    """List of bookings response."""
    bookings: List[BookingResponse]
    total: int
    limit: int
    offset: int


class CancelBookingRequest(BaseModel):
    """Request to cancel a booking."""
    reason: str = Field(default="user_cancelled", max_length=200)


class PaymentInfo(BaseModel):
    """Payment information."""
    payment_id: str
    amount: float
    method: str
    status: str
    transaction_id: Optional[str] = None
    upi_tx_id: Optional[str] = None
    utr_number: Optional[str] = None


class TrainInfo(BaseModel):
    """Train information."""
    train_number: str
    train_name: str
    from_station: str
    to_station: str
    departure_time: str
    arrival_time: str
    duration: str


class BookingDetails(BaseModel):
    """Complete booking details."""
    booking_id: str
    pnr_number: str
    status: BookingStatus
    train_info: TrainInfo
    travel_date: date
    class_type: str
    passengers: List[PassengerDetails]
    total_amount: float
    amount_paid: float
    seats: List[str]
    payment_info: Optional[PaymentInfo] = None
    created_at: datetime
    payment_completed_at: Optional[datetime] = None