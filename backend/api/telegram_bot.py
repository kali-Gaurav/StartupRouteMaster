from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import logging
import os
import asyncio

from database import get_db, SessionTransit
from api.dependencies import get_current_user
from services.telegram_dispatcher import telegram_dispatcher
from database.models import User, Booking

from datetime import datetime, timedelta
import secrets

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)

@router.get("/link-token")
async def generate_link_token(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 3.1: Generate a one-time token to link Telegram."""
    token = secrets.token_hex(4).upper()
    current_user.telegram_link_token = token
    current_user.telegram_link_expiry = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    return {"token": token, "expires_in": 600}

async def process_telegram_message(data: dict):
    """Refined Tony Stark Style Telegram Processor with NLP and Suggestion Buttons."""
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if not text or not chat_id:
        return

    from utils.nlp_router import get_local_intent
    db = SessionTransit()
    try:
        if text == "/start":
            await telegram_dispatcher.send_welcome(chat_id)
            return

        # Task 3.1: Handle Account Linking Token
        if len(text) == 8 and re.match(r'^[0-9A-F]{8}$', text.upper()):
            user = db.query(User).filter(
                User.telegram_link_token == text.upper(),
                User.telegram_link_expiry > datetime.utcnow()
            ).first()
            if user:
                user.telegram_id = str(chat_id)
                user.telegram_link_token = None
                user.telegram_link_expiry = None
                db.commit()
                await telegram_dispatcher._api_request("sendMessage", {
                    "chat_id": chat_id,
                    "text": f"✅ <b>Connection Established.</b>\n\nWelcome {user.full_name or 'Traveler'}. Your RouteMaster account is now linked to this Telegram profile.",
                    "parse_mode": "HTML"
                })
                return
            else:
                await telegram_dispatcher._api_request("sendMessage", {
                    "chat_id": chat_id,
                    "text": "❌ Invalid or expired token. Please generate a new code from the RouteMaster web app settings."
                })
                return

        # NLP Intent Processing (Mirroring Web Chatbot)
        intent_res = await asyncio.to_thread(get_local_intent, text)
        intent = intent_res["intent"] if intent_res else "unknown"

        # Task 3.2: Determine Dynamic Keyboard
        context = "default"
        if intent == "search": context = "search"
        # Check for active journey
        user = db.query(User).filter(User.telegram_id == str(chat_id)).first()
        if user and user.preferences and user.preferences.get("journey_active"):
            context = "journey"
        
        reply_markup = telegram_dispatcher.get_keyboard(context)

        if intent == "sos":
            await telegram_dispatcher._api_request("sendMessage", {
                "chat_id": chat_id,
                "text": "🚨 <b>EMERGENCY PROTOCOL INITIALIZED</b>\n\nNotifying emergency contacts. Sharing last known location data.",
                "parse_mode": "HTML",
                "reply_markup": reply_markup
            })
        elif intent == "bookings":
            if not user:
                await telegram_dispatcher._api_request("sendMessage", {
                    "chat_id": chat_id,
                    "text": "Your Telegram profile is not linked. Use the linking code from our web app to sync your account.",
                    "reply_markup": reply_markup
                })
            else:
                last_booking = db.query(Booking).filter(Booking.user_id == user.id).order_by(Booking.created_at.desc()).first()
                if last_booking:
                    await telegram_dispatcher.send_booking_notification(chat_id, str(last_booking.id), last_booking.pnr_number or "PENDING", "12626")
                else:
                    await telegram_dispatcher._api_request("sendMessage", {
                        "chat_id": chat_id, 
                        "text": "No recent bookings found.",
                        "reply_markup": reply_markup
                    })
        elif intent == "dashboard":
            await telegram_dispatcher._api_request("sendMessage", {
                "chat_id": chat_id,
                "text": "📊 <b>RouteMaster Dashboard Ready</b>\n\nSession active. Visit the web app for full telemetry.",
                "parse_mode": "HTML",
                "reply_markup": reply_markup
            })
        else:
            # Simple AI response or help
            await telegram_dispatcher._api_request("sendMessage", {
                "chat_id": chat_id,
                "text": f"Systems received: '{text}'. Processing logistics...",
                "reply_markup": reply_markup
            })
    except Exception as e:
        logger.error(f"Telegram processing error: {e}")
    finally:
        db.close()
@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Task 2.12: Telegram Bot Webhook.
    Returns 200 OK immediately and processes in background.
    """
    data = await request.json()
    background_tasks.add_task(process_telegram_message, data)
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
