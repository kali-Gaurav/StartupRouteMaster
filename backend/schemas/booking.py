from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from database.models import EscrowStatus, BookingStatus

class BookingResponseSchema(BaseModel):
    id: str
    user_id: str
    pnr_number: Optional[str] = None
    booking_status: Any # Using Any to avoid complex Enum issues with Pydantic v2 if needed, but let's try BookingStatus first
    escrow_status: EscrowStatus
    escrow_message: Optional[str] = None
    amount_paid: float
    upi_tx_id: Optional[str] = None
    utr_number: Optional[str] = None
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

    class Config:
        from_attributes = True

class SubmitUtrSchema(BaseModel):
    utr_number: str = Field(..., min_length=12, max_length=12, pattern=r"^\d{12}$")

class EscrowBookingCreateSchema(BaseModel):
    passenger_name: str
    passenger_age: int
    train_number: str
    amount: float
