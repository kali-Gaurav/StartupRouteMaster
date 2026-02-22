from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import os
import logging
from datetime import datetime

# Import our modules
from .database import get_db, SessionLocal
from .models import Notification, NotificationType, NotificationStatus

# Third-party services
try:
    from twilio.rest import Client as TwilioClient
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
except ImportError:
    TwilioClient = None
    SendGridAPIClient = None
    Mail = None

app = FastAPI(title="Notification Service", version="1.0.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@railwayintelligence.com")

# Initialize clients
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TwilioClient else None
sendgrid_client = SendGridAPIClient(SENDGRID_API_KEY) if SendGridAPIClient else None

# Pydantic models
class NotificationRequest(BaseModel):
    user_id: int
    type: NotificationType
    subject: Optional[str] = None
    message: str
    recipient: str  # email or phone number
    booking_id: Optional[int] = None

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: NotificationType
    subject: Optional[str]
    message: str
    recipient: str
    status: NotificationStatus
    created_at: datetime
    booking_id: Optional[int]

class BulkNotificationRequest(BaseModel):
    notifications: List[NotificationRequest]

# Helper functions
def send_email_via_sendgrid(to_email: str, subject: str, message: str) -> str:
    """Send email using SendGrid"""
    if not sendgrid_client:
        raise HTTPException(status_code=500, detail="SendGrid client not configured")

    mail = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=message
    )

    try:
        response = sendgrid_client.send(mail)
        return str(response.status_code)
    except Exception as e:
        logger.error(f"SendGrid error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

def send_sms_via_twilio(to_phone: str, message: str) -> str:
    """Send SMS using Twilio"""
    if not twilio_client:
        raise HTTPException(status_code=500, detail="Twilio client not configured")

    try:
        message = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=to_phone
        )
        return message.sid
    except Exception as e:
        logger.error(f"Twilio error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")

async def send_notification_async(notification_id: int, db: Session):
    """Background task to send notification"""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        logger.error(f"Notification {notification_id} not found")
        return

    try:
        if notification.type == NotificationType.EMAIL:
            external_id = send_email_via_sendgrid(
                notification.recipient,
                notification.subject or "Railway Intelligence Update",
                notification.message
            )
        elif notification.type == NotificationType.SMS:
            external_id = send_sms_via_twilio(notification.recipient, notification.message)
        else:
            raise ValueError(f"Unsupported notification type: {notification.type}")

        # Update notification status
        notification.status = NotificationStatus.SENT
        notification.external_id = external_id
        notification.sent_at = datetime.utcnow()
        db.commit()

        logger.info(f"Notification {notification_id} sent successfully")

    except Exception as e:
        logger.error(f"Failed to send notification {notification_id}: {e}")
        notification.status = NotificationStatus.FAILED
        notification.error_message = str(e)
        db.commit()

# API endpoints
@app.post("/notifications/", response_model=NotificationResponse)
async def create_notification(
    request: NotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create and send a notification"""
    # Create notification record
    notification = Notification(
        user_id=request.user_id,
        type=request.type,
        subject=request.subject,
        message=request.message,
        recipient=request.recipient,
        booking_id=request.booking_id
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    # Send notification in background
    background_tasks.add_task(send_notification_async, notification.id, db)

    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        type=notification.type,
        subject=notification.subject,
        message=notification.message,
        recipient=notification.recipient,
        status=notification.status,
        created_at=notification.created_at,
        booking_id=notification.booking_id
    )

@app.post("/notifications/bulk/")
async def create_bulk_notifications(
    request: BulkNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create and send multiple notifications"""
    created_notifications = []

    for notif_request in request.notifications:
        notification = Notification(
            user_id=notif_request.user_id,
            type=notif_request.type,
            subject=notif_request.subject,
            message=notif_request.message,
            recipient=notif_request.recipient,
            booking_id=notif_request.booking_id
        )

        db.add(notification)
        created_notifications.append(notification)

    db.commit()

    # Send all notifications in background
    for notification in created_notifications:
        background_tasks.add_task(send_notification_async, notification.id, db)

    return {"message": f"Created {len(created_notifications)} notifications"}

@app.get("/notifications/{notification_id}", response_model=NotificationResponse)
async def get_notification(notification_id: int, db: Session = Depends(get_db)):
    """Get notification by ID"""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        type=notification.type,
        subject=notification.subject,
        message=notification.message,
        recipient=notification.recipient,
        status=notification.status,
        created_at=notification.created_at,
        booking_id=notification.booking_id
    )

@app.get("/notifications/user/{user_id}")
async def get_user_notifications(user_id: int, db: Session = Depends(get_db)):
    """Get all notifications for a user"""
    notifications = db.query(Notification).filter(Notification.user_id == user_id).all()

    return [
        NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            type=n.type,
            subject=n.subject,
            message=n.message,
            recipient=n.recipient,
            status=n.status,
            created_at=n.created_at,
            booking_id=n.booking_id
        ) for n in notifications
    ]

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

# Webhook endpoints for delivery confirmations
@app.post("/webhooks/twilio")
async def twilio_webhook(data: dict):
    """Handle Twilio delivery status webhooks"""
    logger.info(f"Twilio webhook received: {data}")
    # Update notification status based on delivery status
    return {"status": "received"}

@app.post("/webhooks/sendgrid")
async def sendgrid_webhook(data: dict):
    """Handle SendGrid delivery status webhooks"""
    logger.info(f"SendGrid webhook received: {data}")
    # Update notification status based on delivery status
    return {"status": "received"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)