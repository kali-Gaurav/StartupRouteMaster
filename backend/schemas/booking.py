from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from database.models import EscrowStatus, BookingStatus

class BookingResponseSchema(BaseModel):
    # Task 28: Optimized Pydantic V2 Model
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True
    )

    id: str
    user_id: str
    pnr_number: Optional[str] = None
    booking_status: Any 
    escrow_status: EscrowStatus
    escrow_message: Optional[str] = None
    amount_paid: float
    upi_tx_id: Optional[str] = None
    utr_number: Optional[str] = None
    merchant_vpa: Optional[str] = None
    transaction_history: Optional[List[Dict[str, Any]]] = None
    is_tatkal: bool
    priority: int
    service_type: str
    is_unlocked: bool
    agent_id: Optional[str] = None
    train_number: Optional[str] = None
    berth_preference: Optional[str] = None
    booking_details: Optional[Dict[str, Any]] = None
    route_id: Optional[str] = None
    trip_id: Optional[int] = None
    created_at: datetime

class SubmitUtrSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    utr_number: str = Field(..., min_length=12, max_length=12, pattern=r"^\d{12}$")

class EscrowBookingCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    passenger_name: str
    passenger_age: int
    train_number: str
    amount: float

class IRCTCLinkRequest(BaseModel):
    train_number: str
    from_code: str
    to_code: str
    date: str  # YYYY-MM-DD

class IRCTCLinkResponse(BaseModel):
    url: str

class SavePNRRequest(BaseModel):
    journey_id: str
    segment_index: int
    train_number: str
    pnr: str

class SegmentPNRResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    journey_id: str
    segment_index: int
    train_number: str
    pnr: str
    status: str
    created_at: datetime
