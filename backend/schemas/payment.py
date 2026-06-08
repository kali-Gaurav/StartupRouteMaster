"""
Payment Schemas - Pydantic models for payment API.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class PaymentStatus(str, Enum):
    """Payment status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    UNKNOWN = "unknown"


class PaymentMethod(str, Enum):
    """Payment method values."""
    UPI = "upi"
    CARD = "card"
    NET_BANKING = "net_banking"


class PaymentRequest(BaseModel):
    """Request to initiate payment."""
    booking_id: str
    amount: float = Field(..., gt=0)
    payment_method: PaymentMethod
    return_url: Optional[str] = None


class PaymentResponse(BaseModel):
    """Payment response."""
    payment_id: str
    booking_id: str
    amount: float
    status: PaymentStatus
    payment_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[dict] = None
    
    class Config:
        from_attributes = True


class PaymentWebhookPayload(BaseModel):
    """Payment webhook payload."""
    payment_id: str
    status: str
    transaction_id: Optional[str] = None
    upi_tx_id: Optional[str] = None
    utr_number: Optional[str] = None
    amount: Optional[float] = None
    provider: Optional[str] = None
    timestamp: Optional[datetime] = None


class RefundRequest(BaseModel):
    """Refund request."""
    payment_id: str
    amount: Optional[float] = Field(None, gt=0)
    reason: str = Field(..., max_length=200)


class RefundResponse(BaseModel):
    """Refund response."""
    refund_id: str
    original_payment_id: str
    amount: float
    status: PaymentStatus
    reason: str
    processed_at: datetime


class PaymentListResponse(BaseModel):
    """List of payments response."""
    payments: List[PaymentResponse]
    total: int


class ReconciliationReport(BaseModel):
    """Payment reconciliation report."""
    period: dict
    summary: dict
    by_status: dict
    by_method: dict