from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import logging
import asyncio
import re
from typing import Optional

from database import get_db, SessionTransit
from database.config import Config
from api.dependencies import get_current_user
from services.telegram_dispatcher import telegram_dispatcher
from services.search_service import SearchService
from database.models import User, Booking
from schemas.telegram_bot_schemas import Update # Import the Update schema
from utils.nlp_router import get_local_intent

from datetime import datetime, timedelta
import secrets

from services.command_handlers.command_handler import command_handler

# Helper to wrap async handlers for CommandHandler
def async_handler_wrapper(async_func):
    def wrapper(chat_id, args, db_session):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.create_task(async_func(chat_id, args, db_session))
        return None
    return wrapper

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)

FRONTEND_URL = Config._get_env("FRONTEND_URL", "https://safesafar.app")
TELEGRAM_WEBHOOK_SECRET = Config._get_env("TELEGRAM_WEBHOOK_SECRET", None)

# --- Command Handlers ---

async def _send_search_results(chat_id: int, source: str, destination: str, travel_date: str, db_session: Session):
    service = SearchService(db_session)
    try:
        result = await service.search_routes(
            source=source,
            destination=destination,
            travel_date=travel_date,
            limit=3
        )
    except Exception as e:
        logger.error(f"Telegram search failed: {e}")
        return await telegram_dispatcher.send_message(
            chat_id,
            "Sorry, I could not complete the search right now. Please try again later.",
            reply_markup=telegram_dispatcher.get_keyboard("default")
        )

    journeys = result.get("journeys") if isinstance(result, dict) else None
    if not journeys:
        return await telegram_dispatcher.send_message(
            chat_id,
            "I couldn't find any routes for that journey. Please try a different date or route.",
            reply_markup=telegram_dispatcher.get_keyboard("default")
        )

    lines = [f"<b>Search Results for {source} → {destination} on {travel_date}</b>\n"]
    for idx, journey in enumerate(journeys[:3], start=1):
        name = journey.get("train_name") or journey.get("route_name") or journey.get("train_number", "Train")
        dep = journey.get("departure_time") or journey.get("dep_time") or journey.get("start_time", "N/A")
        arr = journey.get("arrival_time") or journey.get("arr_time") or journey.get("end_time", "N/A")
        seats = journey.get("available_seats") or journey.get("seats") or "N/A"
        price = journey.get("fare") or journey.get("price") or "N/A"
        lines.append(
            f"{idx}. {name}\nDep: {dep} · Arr: {arr}\nSeats: {seats} · Fare: {price}\n"
        )

    lines.append("\nReply with a new route or use /bookings to check your bookings.")
    return await telegram_dispatcher.send_message(
        chat_id,
        "\n".join(lines),
        reply_markup=telegram_dispatcher.get_keyboard("default")
    )


def _clean_pnr(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())[:10]


def _extract_travel_date(text: str) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)
    match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", text)
    if match:
        day, month, year = match.group(1).split("/")
        return f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"
    return datetime.utcnow().strftime("%Y-%m-%d")


def _format_booking_summary(booking: Booking) -> str:
    details = booking.booking_details or {}
    return (
        f"<b>Booking Details</b>\n"
        f"PNR: {booking.pnr_number or 'N/A'}\n"
        f"Train: {details.get('train_name') or 'N/A'}\n"
        f"From: {details.get('from') or 'N/A'}\n"
        f"To: {details.get('to') or 'N/A'}\n"
        f"Date: {booking.travel_date or 'N/A'}\n"
        f"Status: {booking.booking_status or 'N/A'}\n"
        f"Amount: ₹{booking.amount_paid or 0.0}"
    )


def _get_linking_text() -> str:
    return (
        "🔗 To use RouteMaster fully on Telegram, first link your account:\n"
        "1. Open the RouteMaster web app.\n"
        "2. Go to Settings -> Telegram.\n"
        "3. Generate a one-time link code and start this bot with /start <code>.\n"
        "4. Your account will be linked securely."
    )


async def start_command_handler(chat_id: int, args: str, db_session: Session):
    """Handles the /start command, including deep linking for account linking."""
    if args:
        token_to_check = args.upper()
        user = db_session.query(User).filter(
            User.telegram_link_token == token_to_check,
            User.telegram_link_expiry > datetime.utcnow()
        ).first()
        if user:
            user.telegram_id = str(chat_id)
            user.telegram_link_token = None
            user.telegram_link_expiry = None
            db_session.commit()
            return await telegram_dispatcher.send_message(
                chat_id,
                f"✅ <b>Connection Established.</b>\n\nWelcome {user.full_name or 'Traveler'}. Your RouteMaster account is now linked to this Telegram profile.",
                reply_markup=telegram_dispatcher.get_keyboard("default")
            )

        return await telegram_dispatcher.send_message(
            chat_id,
            "❌ Invalid or expired token. Please generate a new code from the RouteMaster web app settings.",
            reply_markup=telegram_dispatcher.get_keyboard("help")
        )

    return await telegram_dispatcher.send_welcome(chat_id)


async def help_command_handler(chat_id: int, args: str, db_session: Session):
    """Handles the /help command."""
    help_message = (
        "Hello! I am your RouteMaster AI assistant.\n\n"
        "Use these commands to control your travel from Telegram:\n"
        "/start - Start or link your account.\n"
        "/search - Search trains by route, e.g. Mumbai to Delhi.\n"
        "/bookings - View recent bookings.\n"
        "/pnr - Check PNR status.\n"
        "/cancel - Request cancellation guidance.\n"
        "/sos - Trigger emergency support.\n"
        "/dashboard - Open your RouteMaster dashboard.\n"
        "/help - Show this help message."
    )
    return await telegram_dispatcher.send_message(
        chat_id,
        help_message,
        reply_markup=telegram_dispatcher.get_keyboard("help")
    )


async def search_command_handler(chat_id: int, args: str, db_session: Session):
    if not args:
        return await telegram_dispatcher.send_message(
            chat_id,
            "Please tell me your route like 'Mumbai to Delhi on 2026-05-01'.",
            reply_markup=telegram_dispatcher.get_keyboard("default")
        )

    intent_res = await asyncio.to_thread(get_local_intent, args)
    if intent_res and intent_res.get("intent") == "search" and intent_res.get("entities"):
        entities = intent_res["entities"]
        source = entities.get("source")
        destination = entities.get("destination")
        travel_date = _extract_travel_date(args)
        if source and destination:
            return await _send_search_results(chat_id, source, destination, travel_date, db_session)

    return await telegram_dispatcher.send_message(
        chat_id,
        "I couldn't understand that search request. Please try again like 'Delhi to Mumbai tomorrow'.",
        reply_markup=telegram_dispatcher.get_keyboard("default")
    )


async def pnr_command_handler(chat_id: int, args: str, db_session: Session):
    pnr = _clean_pnr(args or "")
    if not pnr:
        return await telegram_dispatcher.send_message(
            chat_id,
            "Please send a valid 10-digit PNR number, for example: /pnr 1234567890.",
            reply_markup=telegram_dispatcher.get_keyboard("default")
        )

    booking = db_session.query(Booking).filter(Booking.pnr_number == pnr).first()
    if booking:
        return await telegram_dispatcher.send_message(
            chat_id,
            _format_booking_summary(booking),
            reply_markup=telegram_dispatcher.get_keyboard("journey")
        )

    return await telegram_dispatcher.send_message(
        chat_id,
        "I could not find a booking for that PNR. Please check the number or search for a route first.",
        reply_markup=telegram_dispatcher.get_keyboard("default")
    )


async def bookings_command_handler(chat_id: int, args: str, db_session: Session):
    user = db_session.query(User).filter(User.telegram_id == str(chat_id)).first()
    if not user:
        return await telegram_dispatcher.send_message(
            chat_id,
            _get_linking_text(),
            reply_markup=telegram_dispatcher.get_keyboard("help")
        )

    bookings = db_session.query(Booking).filter(Booking.user_id == user.id).order_by(Booking.created_at.desc()).limit(3).all()
    if not bookings:
        return await telegram_dispatcher.send_message(
            chat_id,
            "You are linked, but I couldn't find recent bookings. Visit your dashboard to view complete history.",
            reply_markup=telegram_dispatcher.get_keyboard("default")
        )

    lines = ["<b>Your recent bookings</b>\n"]
    for booking in bookings:
        lines.append(
            f"PNR: {booking.pnr_number or 'N/A'} | Date: {booking.travel_date or 'N/A'} | Status: {booking.booking_status or 'N/A'}"
        )
    lines.append("\nReply with /pnr <number> for details.")

    return await telegram_dispatcher.send_message(
        chat_id,
        "\n".join(lines),
        reply_markup=telegram_dispatcher.get_keyboard("default")
    )


async def cancel_command_handler(chat_id: int, args: str, db_session: Session):
    user = db_session.query(User).filter(User.telegram_id == str(chat_id)).first()
    if not user:
        return await telegram_dispatcher.send_message(
            chat_id,
            _get_linking_text(),
            reply_markup=telegram_dispatcher.get_keyboard("help")
        )

    booking = db_session.query(Booking).filter(Booking.user_id == user.id).order_by(Booking.created_at.desc()).first()
    if booking:
        return await telegram_dispatcher.send_message(
            chat_id,
            f"I found your latest booking (PNR: {booking.pnr_number or 'N/A'}). To cancel or raise a refund request, please use your dashboard: {FRONTEND_URL}/bookings.",
            reply_markup=telegram_dispatcher.get_keyboard("help")
        )

    return await telegram_dispatcher.send_message(
        chat_id,
        "No booking was found for your account. Please check your dashboard or provide a PNR number with /pnr.",
        reply_markup=telegram_dispatcher.get_keyboard("default")
    )


async def sos_command_handler(chat_id: int, args: str, db_session: Session):
    user = db_session.query(User).filter(User.telegram_id == str(chat_id)).first()
    if not user:
        return await telegram_dispatcher.send_message(
            chat_id,
            "Emergency assistance is available once your account is linked. Please link the bot from the web app first.",
            reply_markup=telegram_dispatcher.get_keyboard("help")
        )

    await telegram_dispatcher.send_message(
        chat_id,
        "✅ SOS has been received. Help is being notified.",
        reply_markup=telegram_dispatcher.get_keyboard("journey")
    )
    admin_chat = Config._get_env("TELEGRAM_CHAT_ID")
    if admin_chat:
        await telegram_dispatcher.send_message(
            admin_chat,
            f"🚨 SOS Alert from {user.full_name or 'Traveler'} (Telegram ID: {chat_id}). Please review the dashboard immediately."
        )


async def dashboard_command_handler(chat_id: int, args: str, db_session: Session):
    return await telegram_dispatcher.send_message(
        chat_id,
        f"📊 Open your RouteMaster dashboard here: {FRONTEND_URL}/dashboard",
        reply_markup=telegram_dispatcher.get_keyboard("default")
    )


async def help_text_handler(chat_id: int, args: str, db_session: Session):
    return await help_command_handler(chat_id, args, db_session)


async def default_message_handler(chat_id: int, text: str, db_session: Session):
    from utils.nlp_router import get_local_intent

    intent_res = await asyncio.to_thread(get_local_intent, text)
    intent = intent_res["intent"] if intent_res else "unknown"
    context = "default"
    user = db_session.query(User).filter(User.telegram_id == str(chat_id)).first()
    if user is not None and user.preferences and user.preferences.get("journey_active"):
        context = "journey"

    reply_markup = telegram_dispatcher.get_keyboard(context)

    if intent == "sos":
        return await sos_command_handler(chat_id, text, db_session)
    if intent == "bookings":
        return await bookings_command_handler(chat_id, text, db_session)
    if intent == "dashboard":
        return await dashboard_command_handler(chat_id, text, db_session)
    if intent == "pnr":
        pnr = intent_res.get("entities", {}).get("pnr") if intent_res else None
        return await pnr_command_handler(chat_id, pnr or text, db_session)
    if intent == "search":
        return await search_command_handler(chat_id, text, db_session)
    if intent == "cancel":
        return await cancel_command_handler(chat_id, text, db_session)
    if intent == "help" or intent == "greet":
        return await help_command_handler(chat_id, text, db_session)

    return await telegram_dispatcher.send_message(
        chat_id,
        f"I received your message: '{text}'. You can ask me to search trains, check PNR, view bookings, or trigger SOS.",
        reply_markup=reply_markup
    )


def _parse_callback_data(data: str):
    return data.strip().lower() if data else ""


async def process_callback_query(callback_query, db_session: Session):
    chat_id = callback_query.message.chat.id if callback_query.message else None
    if not chat_id:
        return

    answer_payload = {
        "callback_query_id": callback_query.id,
        "text": "Processing...",
        "show_alert": False
    }
    await telegram_dispatcher._api_request("answerCallbackQuery", answer_payload)
    action = _parse_callback_data(callback_query.data)

    if action == "search_trains":
        return await telegram_dispatcher.send_message(
            chat_id,
            "Please tell me the route you want to search. Example: Delhi to Mumbai tomorrow.",
            reply_markup=telegram_dispatcher.get_keyboard("default")
        )
    if action == "my_bookings":
        return await bookings_command_handler(chat_id, "", db_session)
    if action == "dashboard":
        return await dashboard_command_handler(chat_id, "", db_session)
    if action == "sos":
        return await sos_command_handler(chat_id, "", db_session)
    if action == "help":
        return await help_command_handler(chat_id, "", db_session)

    return await telegram_dispatcher.send_message(
        chat_id,
        "Action received. Please type a command or describe your travel needs.",
        reply_markup=telegram_dispatcher.get_keyboard("default")
    )


# Register commands with the CommandHandler
command_handler.register_command("/start", async_handler_wrapper(start_command_handler))
command_handler.register_command("/help", async_handler_wrapper(help_command_handler))
command_handler.register_command("/search", async_handler_wrapper(search_command_handler))
command_handler.register_command("/pnr", async_handler_wrapper(pnr_command_handler))
command_handler.register_command("/bookings", async_handler_wrapper(bookings_command_handler))
command_handler.register_command("/cancel", async_handler_wrapper(cancel_command_handler))
command_handler.register_command("/sos", async_handler_wrapper(sos_command_handler))
command_handler.register_command("/dashboard", async_handler_wrapper(dashboard_command_handler))
command_handler.register_default_handler(async_handler_wrapper(default_message_handler))

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

async def process_telegram_message(update: Update):
    """
    Main processor for incoming Telegram updates.
    Handles both message updates and callback queries.
    """
    if update.callback_query:
        db = SessionTransit()
        try:
            await process_callback_query(update.callback_query, db_session=db)
        except Exception as e:
            logger.error(f"Telegram callback processing error: {e}")
        finally:
            db.close()
        return

    if not update.message:
        logger.warning("Received Telegram update with no message field.")
        return

    message = update.message
    text = message.text
    chat_id = message.chat.id

    if not text or not chat_id:
        return

    db = SessionTransit()
    try:
        await command_handler.handle_message(chat_id, text, db_session=db)
    except Exception as e:
        logger.error(f"Telegram processing error: {e}")
    finally:
        db.close()

@router.post("/webhook")
async def telegram_webhook(request: Request, update: Update, background_tasks: BackgroundTasks):
    """
    Task 2.12: Telegram Bot Webhook.
    Receives and validates Telegram updates, then processes them in the background.
    """
    if TELEGRAM_WEBHOOK_SECRET:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header != TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden: invalid webhook secret token.")

    background_tasks.add_task(process_telegram_message, update)
    return {"ok": True}

@router.post("/link")
async def link_telegram(
    telegram_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Link a Telegram chat ID to the current authenticated user."""
    existing = db.query(User).filter(User.telegram_id == telegram_id).first()
    if existing and existing.id != current_user.id:
        raise HTTPException(status_code=400, detail="This Telegram account is already linked to another user.")

    current_user.telegram_id = telegram_id
    db.commit()
    logger.info(f"Linked Telegram ID {telegram_id} to user {current_user.id}")
    return {"success": True, "message": "Telegram account linked successfully."}

