from core.celery_app import celery
import logging

logger = logging.getLogger(__name__)

@celery.task(name="send_booking_email")
def send_booking_email(user_email, booking_id):
    """
    Background task to simulate sending a booking confirmation email.
    """
    logger.info(f"Sending booking email for ID: {booking_id} to {user_email}")
    # In a real scenario, integrate with SendGrid or Twilio here.
    return {"status": "sent", "email": user_email, "booking_id": booking_id}
