"""
Notification Service - Multi-channel notification delivery.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import select

from database.models import Notification, NotificationPreference
from schemas.notification import NotificationType, NotificationChannel

logger = logging.getLogger("notification_service")


@dataclass
class NotificationResult:
    """Result of notification send attempt."""
    success: bool
    channel: str
    message_id: Optional[str] = None
    error: Optional[str] = None


class NotificationService:
    """Multi-channel notification service."""
    
    def __init__(self, db: Session):
        self.db = db
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Dict]:
        """Load notification templates."""
        return {
            "booking_confirmed": {
                "sms": "Your booking {pnr} is confirmed! Train {train} from {from} to {to} on {date}. Have a safe journey!",
                "email": "Booking Confirmation - Your trip is confirmed!",
                "push": "Booking {pnr} confirmed for {date}"
            },
            "payment_received": "Payment of ₹{amount} received for booking {pnr}. Thank you!",
            "pnr_status": "PNR {pnr} status update: {status}",
            "delay_alert": "Alert: Train {train} is delayed by {delay} minutes. New arrival time: {new_time}",
            "safety_alert": "Safety Alert: {message}",
            "booking_initiated": "Your booking request for {pnr} is being processed. Complete payment within {time} minutes."
        }
    
    async def queue_notification(
        self,
        user_id: str,
        notification_type: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Queue a notification for delivery.
        
        Args:
            user_id: Target user ID
            notification_type: Type of notification
            data: Template variables
            
        Returns:
            Notification ID
        """
        notification_id = str(datetime.now().timestamp()).replace(".", "")[:12]
        
        notification = Notification(
            id=notification_id,
            user_id=user_id,
            notification_type=notification_type,
            data=data,
            status="queued",
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(notification)
        self.db.commit()
        
        # Process asynchronously in production
        return notification_id
    
    async def send_notification(
        self,
        user_id: str,
        notification_type: str,
        channels: List[str] = ["sms", "email", "push"],
        data: Optional[Dict[str, Any]] = None
    ) -> List[NotificationResult]:
        """
        Send notification through specified channels.
        
        Args:
            user_id: Target user ID
            notification_type: Type of notification
            channels: List of channels to use
            data: Template variables
            
        Returns:
            List of results per channel
        """
        results = []
        data = data or {}
        
        # Get user preferences
        prefs = await self.get_user_preferences(user_id)
        
        for channel in channels:
            # Check if channel is enabled
            if channel == "sms" and not prefs.get("sms_enabled", True):
                results.append(NotificationResult(success=False, channel=channel, error="SMS disabled"))
                continue
            if channel == "email" and not prefs.get("email_enabled", True):
                results.append(NotificationResult(success=False, channel=channel, error="Email disabled"))
                continue
            if channel == "push" and not prefs.get("push_enabled", True):
                results.append(NotificationResult(success=False, channel=channel, error="Push disabled"))
                continue
            if channel == "telegram" and not prefs.get("telegram_enabled", True):
                results.append(NotificationResult(success=False, channel=channel, error="Telegram disabled"))
                continue

            # Send based on channel
            if channel == "sms":
                result = await self._send_sms(user_id, notification_type, data)
            elif channel == "email":
                result = await self._send_email(user_id, notification_type, data)
            elif channel == "push":
                result = await self._send_push(user_id, notification_type, data)
            elif channel == "telegram":
                result = await self._send_telegram(user_id, notification_type, data)
            else:
                result = NotificationResult(success=False, channel=channel, error="Unknown channel")

            results.append(result)
        
        return results
    
    async def _send_sms(
        self,
        user_id: str,
        notification_type: str,
        data: Dict[str, Any]
    ) -> NotificationResult:
        """Send SMS notification via Twilio."""
        try:
            # Get user phone
            from database.models import User
            user = self.db.get(User, user_id)
            phone = user.phone if user else None

            if not phone:
                return NotificationResult(success=False, channel="sms", error="No phone number")

            # Get template
            template = self.templates.get(notification_type, {}).get("sms", "")
            if isinstance(template, dict):
                template = template.get("sms", "")

            # Format message
            message = template.format(**data)

            # Send via Twilio provider
            from services.sms_provider import get_sms_provider
            provider = get_sms_provider()
            result = await provider.send(phone, message)

            if result.success:
                logger.info(f"SMS sent to {phone} via Twilio: {result.message_id}")
            else:
                logger.error(f"SMS send failed: {result.error}")

            return NotificationResult(
                success=result.success,
                channel="sms",
                message_id=result.message_id,
                error=result.error
            )

        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return NotificationResult(success=False, channel="sms", error=str(e))
    
    async def _send_email(
        self,
        user_id: str,
        notification_type: str,
        data: Dict[str, Any]
    ) -> NotificationResult:
        """Send email notification via Mailgun."""
        try:
            from database.models import User
            user = self.db.get(User, user_id)
            email = user.email if user else None

            if not email:
                return NotificationResult(success=False, channel="email", error="No email")

            # Get template and subject
            template_data = self.templates.get(notification_type, {})
            if isinstance(template_data, dict):
                template = template_data.get("email", "")
            else:
                template = template_data

            # Format subject and body
            subject = f"RouteMaster - {notification_type.replace('_', ' ').title()}"
            body = template.format(**data)

            # Send via Mailgun provider
            from services.email_provider import get_email_provider
            provider = get_email_provider()
            result = await provider.send(
                to=email,
                subject=subject,
                text=body,
                tags=[notification_type, "transactional"]
            )

            if result.success:
                logger.info(f"Email sent to {email} via Mailgun: {result.message_id}")
            else:
                logger.error(f"Email send failed: {result.error}")

            return NotificationResult(
                success=result.success,
                channel="email",
                message_id=result.message_id,
                error=result.error
            )

        except Exception as e:
            logger.error(f"Email send error: {e}")
            return NotificationResult(success=False, channel="email", error=str(e))
    
    async def _send_push(
        self,
        user_id: str,
        notification_type: str,
        data: Dict[str, Any]
    ) -> NotificationResult:
        """Send push notification."""
        try:
            # In production, integrate with push service (Firebase, etc.)
            logger.info(f"Push to user {user_id}: {notification_type}")
            
            return NotificationResult(
                success=True,
                channel="push",
                message_id=f"push_{datetime.now().timestamp()}"
            )
            
        except Exception as e:
            logger.error(f"Push send error: {e}")
            return NotificationResult(success=False, channel="push", error=str(e))

    async def _send_telegram(
        self,
        user_id: str,
        notification_type: str,
        data: Dict[str, Any]
    ) -> NotificationResult:
        """Send notification via Telegram Bot API."""
        try:
            import httpx
            import os

            from database.models import User

            # Get user
            user = self.db.get(User, user_id)
            if not user or not user.telegram_id:
                return NotificationResult(success=False, channel="telegram", error="User has no Telegram ID")

            # Get bot token
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            if not bot_token:
                logger.warning("TELEGRAM_BOT_TOKEN not configured - Telegram notifications disabled")
                return NotificationResult(
                    success=True,
                    channel="telegram",
                    message_id=f"stub_{user.telegram_id}"
                )

            # Get template
            template = self.templates.get(notification_type, {})
            if isinstance(template, dict):
                message = template.get("push", template.get("sms", ""))
            else:
                message = template

            if not message:
                return NotificationResult(success=False, channel="telegram", error="No template found")

            # Format message
            formatted_message = message.format(**data)

            # Format for Telegram (escape HTML special chars)
            formatted_message = formatted_message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            # Add emoji and formatting based on notification type
            emoji_map = {
                "booking_confirmed": "✅",
                "payment_received": "💳",
                "pnr_status": "📋",
                "delay_alert": "⚠️",
                "safety_alert": "🛡️",
            }
            emoji = emoji_map.get(notification_type, "📢")

            final_message = f"{emoji} <b>RouteMaster</b>\n\n{formatted_message}"

            # Send via Telegram Bot API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": user.telegram_id,
                        "text": final_message,
                        "parse_mode": "HTML"
                    },
                    timeout=10.0
                )

                if response.status_code in (200, 201):
                    result = response.json()
                    if result.get("ok"):
                        message_id = result.get("result", {}).get("message_id")
                        logger.info(f"Telegram sent to user {user_id}: {message_id}")
                        return NotificationResult(
                            success=True,
                            channel="telegram",
                            message_id=message_id
                        )
                    else:
                        error = result.get("description", response.text)
                        logger.error(f"Telegram API error: {error}")
                        return NotificationResult(success=False, channel="telegram", error=error)
                else:
                    error = response.text
                    logger.error(f"Telegram send failed: {error}")
                    return NotificationResult(success=False, channel="telegram", error=error)

        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return NotificationResult(success=False, channel="telegram", error=str(e))

    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user notification preferences."""
        result = self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id
            )
        ).scalar_one_or_none()
        
        if result and hasattr(result, 'sms_enabled'):
            return {
                "sms_enabled": result.sms_enabled,
                "email_enabled": result.email_enabled,
                "push_enabled": result.push_enabled,
                "telegram_enabled": getattr(result, 'telegram_enabled', True),
                "booking_confirmed": result.booking_confirmed,
                "payment_received": result.payment_received,
                "pnr_status": result.pnr_status,
                "delay_alerts": result.delay_alerts,
                "safety_alerts": result.safety_alerts,
                "marketing": result.marketing
            }

        # Default preferences
        return {
            "sms_enabled": True,
            "email_enabled": True,
            "push_enabled": True,
            "telegram_enabled": True,
            "booking_confirmed": True,
            "payment_received": True,
            "pnr_status": True,
            "delay_alerts": True,
            "safety_alerts": True,
            "marketing": False
        }
    
    async def update_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update user notification preferences."""
        existing = self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id
            )
        ).scalar_one_or_none()
        
        if existing:
            for key, value in preferences.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
        else:
            existing = NotificationPreference(
                id=str(datetime.now().timestamp()).replace(".", "")[:12],
                user_id=user_id,
                **preferences
            )
            self.db.add(existing)
        
        self.db.commit()
        
        return await self.get_user_preferences(user_id)


# ==================== MOCK NOTIFICATION METHODS FOR DEMO ====================

async def send_sms_stub(
    self,
    phone_number: str,
    message: str
) -> bool:
    """
    Mock SMS sending for demo purposes.
    Logs the SMS instead of sending.
    """
    logger.info(f"[SMS STUB] To: {phone_number}")
    logger.info(f"[SMS STUB] Message: {message}")
    
    # Create notification log
    notification = Notification(
        id=str(datetime.now().timestamp()).replace(".", "")[:12],
        user_id="stub",
        notification_type="sms",
        data={"phone": phone_number, "message": message},
        status="sent",
        created_at=datetime.now(timezone.utc)
    )
    
    self.db.add(notification)
    self.db.commit()
    
    return True

async def send_email_stub(
    self,
    email: str,
    subject: str,
    body: str,
    html: Optional[str] = None
) -> bool:
    """
    Mock email sending for demo purposes.
    Logs the email instead of sending.
    """
    logger.info(f"[EMAIL STUB] To: {email}")
    logger.info(f"[EMAIL STUB] Subject: {subject}")
    logger.info(f"[EMAIL STUB] Body: {body}")
    
    # Create notification log
    notification = Notification(
        id=str(datetime.now().timestamp()).replace(".", "")[:12],
        user_id="stub",
        notification_type="email",
        data={"email": email, "subject": subject, "body": body},
        status="sent",
        created_at=datetime.now(timezone.utc)
    )
    
    self.db.add(notification)
    self.db.commit()
    
    return True

async def send_booking_confirmation(
    self,
    user_id: str,
    booking_id: str,
    pnr_number: str,
    train_details: Dict[str, Any]
) -> bool:
    """
    Send booking confirmation via all channels.
    """
    # Format SMS
    sms_message = f"Booking Confirmed! PNR: {pnr_number}. Train: {train_details.get('train_number')}. Date: {train_details.get('date')}. Safe travels!"
    
    # Format email
    email_subject = f"Booking Confirmed - PNR {pnr_number}"
    email_body = f"""
    Your booking is confirmed!
    
    PNR: {pnr_number}
    Train: {train_details.get('train_number')}
    Date: {train_details.get('date')}
    From: {train_details.get('from')}
    To: {train_details.get('to')}
    
    Show this email at the station.
    """
    
    # Send via stubs
    await self.send_sms_stub("+91XXXXXXXXXX", sms_message)
    await self.send_email_stub("user@example.com", email_subject, email_body)
    
    return True


# Singleton instance
notification_service = None

def get_notification_service(db: Session) -> NotificationService:
    """Get or create notification service instance."""
    global notification_service
    if notification_service is None:
        notification_service = NotificationService(db)
    return notification_service