from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
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
    source: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z\s\-]+$")
    destination: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z\s\-]+$")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    budget: str = Field("all", pattern="^(all|economy|standard|premium)$")
    multi_modal: bool = Field(True, description="Whether to include multi-modal planning suggestions")

    # New fields for advanced features
    journey_type: Optional[str] = Field(None, pattern="^(single|connecting|circular|multi_city)$")
    return_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")  # For circular journeys
    cities: Optional[List[str]] = Field(None, description="List of cities for multi-city booking (max 3)")
    passenger_type: Optional[str] = Field("adult", pattern="^(adult|child|senior|student)$")
    concessions: Optional[List[str]] = Field(None, description="List of concessions (defence, freedom_fighter, divyang)")

    class Config:
        json_schema_extra = {
            "example": {
                "source": "Mumbai Central",
                "destination": "Delhi",
                "date": "2025-12-25",
                "budget": "economy",
                "multi_modal": True,
                "journey_type": "single",
                "passenger_type": "adult",
                "concessions": []
            }
        }


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

    class Config:
        json_schema_extra = {
            "example": {
                "route_id": "550e8400-e29b-41d4-a716-446655440000",
                "travel_date": "2025-12-25",
                "is_unlock_payment": False
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


class BookingResponseSchema(BaseModel):
    id: str
    user: UserRead
    route_id: str
    travel_date: str
    payment_status: str
    amount_paid: float
    created_at: datetime

    class Config:
        from_attributes = True


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
