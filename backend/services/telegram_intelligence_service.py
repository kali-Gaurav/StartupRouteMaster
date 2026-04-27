import logging
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from services.telegram_dispatcher import telegram_dispatcher
from services.telegram_session_manager import session_manager
from database.models import User, TelegramAccount, Booking
from database.config import Config

logger = logging.getLogger("telegram.intelligence")

class TelegramIntelligence:
    """
    Bridge service that pushes proactive intelligence from Web/Backend to Telegram.
    Connects user web behavior to Telegram notifications.
    """

    @staticmethod
    async def generate_magic_link(db: Session, user_id: str) -> str:
        """Generates a one-time secure link to log into the web app."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return ""
        
        # Generate token (in a real app, this would be stored in a 'tokens' table)
        token = f"ml_{uuid.uuid4().hex}"
        frontend_url = Config._get_env("FRONTEND_URL", "https://safesafar.app")
        return f"{frontend_url}/auth/magic?token={token}&target=dashboard"

    @staticmethod
    async def request_crowd_feedback(db: Session, booking_id: str):
        """Asks a traveling user for live crowd updates."""
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return False

        account = db.query(TelegramAccount).filter(TelegramAccount.user_id == booking.user_id, TelegramAccount.is_active == True).first()
        if not account:
            return False

        message = (
            "👂 <b>RouteMaster Community:</b>\n\nYou are currently on your journey! How is the crowd level in your coach?\n\n"
            "Your feedback helps other travelers avoid over-crowded trains."
        )
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🟢 Low (Empty)", "callback_data": "crowd_feedback:low"}],
                [{"text": "🟡 Moderate", "callback_data": "crowd_feedback:moderate"}],
                [{"text": "🔴 High (Packed)", "callback_data": "crowd_feedback:high"}]
            ]
        }
        
        return await telegram_dispatcher.send_message(account.telegram_id, message, reply_markup=keyboard)

    @staticmethod
    async def push_ui_state(db: Session, user_id: str, state_type: str, data: Dict[str, Any]):
        """
        ShadowSync: Mirrors Web UI state to Telegram.
        state_type: 'view_route', 'search_params', 'passenger_draft'
        """
        account = db.query(TelegramAccount).filter(TelegramAccount.user_id == user_id, TelegramAccount.is_active == True).first()
        if not account:
            return False

        if state_type == "view_route":
            train_no = data.get("train_number")
            message = f"👀 <b>ShadowSync:</b> I see you are viewing Train <b>{train_no}</b> on the website. Need a quick PNR check or booking link here?"
            keyboard = {
                "inline_keyboard": [[{"text": "🎫 Quick Book", "callback_data": f"select_train:{train_no}"}]]
            }
            return await telegram_dispatcher.send_message(account.telegram_id, message, reply_markup=keyboard)

        if state_type == "search_params":
            return await TelegramIntelligence.push_handoff_session(db, user_id, data)

    @staticmethod
    async def notify_price_drop(db: Session, user_id: str, train_no: str, old_price: float, new_price: float):
        """Notifies user on Telegram when a watched train price drops."""
        account = db.query(TelegramAccount).filter(TelegramAccount.user_id == user_id, TelegramAccount.is_active == True).first()
        if not account:
            return False

        message = (
            f"📉 <b>Price Drop Alert!</b>\n\n"
            f"Good news! The fare for Train <b>{train_no}</b> has dropped from ₹{old_price} to <b>₹{new_price}</b>.\n"
            f"Book now to save on your journey!"
        )
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🎫 Book Now", "url": f"https://safesafar.app/book?train={train_no}"}],
                [{"text": "🔕 Mute Alerts", "callback_data": "mute_price_alerts"}]
            ]
        }
        
        return await telegram_dispatcher.send_message(account.telegram_id, message, reply_markup=keyboard)

    @staticmethod
    async def push_handoff_session(db: Session, user_id: str, context: Dict[str, Any]):
        """Pushes a web search session to Telegram for 1-click completion."""
        account = db.query(TelegramAccount).filter(TelegramAccount.user_id == user_id, TelegramAccount.is_active == True).first()
        if not account:
            return False

        source = context.get("source")
        dest = context.get("destination")
        
        # Update session state to 'search' so they can continue in Telegram
        session_manager.update_session(
            db, account.telegram_id, account.telegram_id,
            intent="search", 
            step="results", 
            context=context
        )

        message = (
            f"🔄 <b>Continue your search?</b>\n\n"
            f"I see you were looking for trains from <b>{source}</b> to <b>{dest}</b> on the website.\n"
            f"Would you like to see the latest availability here?"
        )
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔍 Show Trains", "callback_data": "continue_last_search"}],
                [{"text": "❌ Not Now", "callback_data": "cancel_flow"}]
            ]
        }
        
        return await telegram_dispatcher.send_message(account.telegram_id, message, reply_markup=keyboard)

    @staticmethod
    async def notify_delay(db: Session, booking_id: str, delay_mins: int):
        """
        Notifies user of train delay with PDR (Predictive Delay Routing).
        If delay is severe, suggests multi-modal alternatives.
        """
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking or not getattr(booking, 'user_id', None):
            return False

        account = db.query(TelegramAccount).filter(TelegramAccount.user_id == booking.user_id, TelegramAccount.is_active == True).first()
        if not account:
            return False

        train_no = getattr(booking, 'train_number', None) or "your train"
        message = [f"⚠️ <b>Delay Update:</b> Train <b>{train_no}</b> is late by <b>{delay_mins}m</b>."]

        keyboard_btns = [[{"text": "📍 Track Live", "callback_data": "track"}]]

        # PDR Algorithm: If delay > 60 mins, suggest alternative
        if delay_mins > 60:
            from services.unified_travel_planner import UnifiedTravelPlanner, TravelRequest
            origin = getattr(booking, 'source_station', None)
            destination = getattr(booking, 'destination_station', None)
            if not origin or not destination:
                message.append("\n💡 Unable to compute alternatives because route data is incomplete.")
                keyboard = {"inline_keyboard": keyboard_btns}
                return await telegram_dispatcher.send_message(account.telegram_id, "\n".join(message), reply_markup=keyboard)

            planner = UnifiedTravelPlanner(db)
            alt_request = TravelRequest(
                origin=str(origin),
                destination=str(destination),
                travel_date=datetime.utcnow().date(),
                allow_multi_modal=True
            )
            alt_plan = await planner.create_travel_plan(alt_request)
            if alt_plan and alt_plan.options:
                best_alt = alt_plan.options[0]
                message.append(f"\n💡 <b>RouteMaster Suggestion:</b> Save time with a <b>{best_alt.option_type}</b> alternative arriving at {best_alt.arrival_time.strftime('%H:%M')}.")
                keyboard_btns.append([{"text": f"🚀 Swap to {best_alt.option_type.title()}", "callback_data": f"select_option:{best_alt.option_id}"}])

        keyboard = {"inline_keyboard": keyboard_btns}
        return await telegram_dispatcher.send_message(account.telegram_id, "\n".join(message), reply_markup=keyboard)

telegram_intelligence = TelegramIntelligence()
