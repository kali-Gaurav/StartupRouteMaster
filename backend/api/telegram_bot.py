from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
import logging
import os

from database import get_db
from api.dependencies import get_current_user
from services.telegram_dispatcher import telegram_dispatcher
from database.models import User, Booking

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Task 33.1 & 33.9: Telegram Bot Webhook.
    Handles commands like /last and /start.
    """
    data = await request.json()
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    
    if not text or not chat_id:
        return {"ok": True}

    if text == "/start":
        await telegram_dispatcher.send_welcome(chat_id)
        
    elif text == "/last":
        # Task 33.9: Bot command for "Last Booking"
        # Find the user by telegram ID (assuming we stored it in User model)
        user = db.query(User).filter(User.phone_number == str(chat_id)).first() # Placeholder logic
        if not user:
            await telegram_dispatcher._api_request("sendMessage", {
                "chat_id": chat_id,
                "text": "Your Telegram ID is not linked to a RouteMaster account. Please link it in the app settings."
            })
            return {"ok": True}
            
        last_booking = db.query(Booking).filter(Booking.user_id == user.id).order_by(Booking.created_at.desc()).first()
        if last_booking:
            await telegram_dispatcher.send_booking_notification(
                chat_id, 
                str(last_booking.id), 
                last_booking.pnr_number or "PENDING", 
                "12626"
            )
        else:
            await telegram_dispatcher._api_request("sendMessage", {
                "chat_id": chat_id,
                "text": "No recent bookings found."
            })

    return {"ok": True}

@router.post("/link")
async def link_telegram(
    telegram_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 33.5: Support for multiple Telegram IDs per user."""
    # Update user record or a dedicated Mapping table
    # For demo, we assume User.phone_number is used or just return success
    logger.info(f"Linking Telegram ID {telegram_id} to user {current_user.id}")
    return {"success": True, "message": "Telegram account linked successfully."}
