"""
Notification Schemas - Pydantic models for notification API.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel


class NotificationType(str, Enum):
    """Notification type values."""
    BOOKING_CONFIRMED = "booking_confirmed"
    PAYMENT_RECEIVED = "payment_received"
    PNR_STATUS = "pnr_status"
    DELAY_ALERT = "delay_alert"
    SAFETY_ALERT = "safety_alert"
    BOOKING_INITIATED = "booking_initiated"


class NotificationChannel(str, Enum):
    """Notification channel values."""
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"


class NotificationCreate(BaseModel):
    """Create notification request."""
    user_id: str
    type: NotificationType
    channels: List[NotificationChannel]
    data: dict
    scheduled_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    """Notification response."""
    id: str
    user_id: str
    type: str
    status: str
    channels: List[str]
    created_at: datetime
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class NotificationPreferenceUpdate(BaseModel):
    """Update notification preferences."""
    sms_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    booking_confirmed: Optional[bool] = None
    payment_received: Optional[bool] = None
    pnr_status: Optional[bool] = None
    delay_alerts: Optional[bool] = None
    safety_alerts: Optional[bool] = None
    marketing: Optional[bool] = None