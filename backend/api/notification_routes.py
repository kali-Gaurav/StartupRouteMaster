"""
Notification API Routes - REST endpoints for notification management.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.session import get_db
from services.notification_service import get_notification_service
from core.auth import get_current_user

logger = logging.getLogger("api")

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class NotificationPreferences(BaseModel):
    """User notification preferences."""
    sms_enabled: bool = True
    email_enabled: bool = True
    push_enabled: bool = True
    booking_confirmed: bool = True
    payment_received: bool = True
    pnr_status: bool = True
    delay_alerts: bool = True
    safety_alerts: bool = True
    marketing: bool = False


@router.get("/preferences")
async def get_notification_preferences(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Get user's notification preferences."""
    service = get_notification_service(db)
    prefs = await service.get_user_preferences(user.id)
    
    return prefs


@router.put("/preferences")
async def update_notification_preferences(
    preferences: NotificationPreferences,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Update user's notification preferences."""
    service = get_notification_service(db)
    result = await service.update_preferences(user.id, preferences.dict())
    
    return {"status": "updated", "preferences": result}


@router.post("/send")
async def send_notification(
    request: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Send a notification (admin only).
    
    Request body:
    - user_id: Target user ID
    - type: Notification type
    - channels: List of channels (sms, email, push)
    - data: Notification data
    """
    service = get_notification_service(db)
    
    result = await service.send_notification(
        user_id=request.get("user_id"),
        notification_type=request.get("type"),
        channels=request.get("channels", ["sms", "email"]),
        data=request.get("data", {})
    )
    
    return result


@router.get("/templates")
async def list_notification_templates():
    """List available notification templates."""
    templates = [
        {
            "id": "booking_confirmed",
            "name": "Booking Confirmed",
            "description": "Sent when booking is confirmed",
            "channels": ["sms", "email", "push"]
        },
        {
            "id": "payment_received",
            "name": "Payment Received",
            "description": "Sent when payment is confirmed",
            "channels": ["sms", "email"]
        },
        {
            "id": "pnr_status",
            "name": "PNR Status Update",
            "description": "Sent when PNR status changes",
            "channels": ["sms", "push"]
        },
        {
            "id": "delay_alert",
            "name": "Delay Alert",
            "description": "Sent when train is delayed",
            "channels": ["sms", "push", "email"]
        },
        {
            "id": "safety_alert",
            "name": "Safety Alert",
            "description": "Sent for safety-related alerts",
            "channels": ["sms", "push"]
        }
    ]
    
    return {"templates": templates}