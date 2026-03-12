import httpx
import logging
import io
from typing import Optional, List, Union, Dict, Any
from database.config import Config

logger = logging.getLogger(__name__)

class TelegramDispatcher:
    """
    Task 33: Telegram Standalone Dispatcher.
    Handles booking notifications, PDF deliveries, and inline bot commands.
    """
    
    def __init__(self):
        self.bot_token = Config.TELEGRAM_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_booking_notification(self, chat_id: Union[str, int], booking_id: str, pnr: str, train_no: str):
        """
        Task 33.2: Instant PNR Notification.
        Task 33.8: Rich-text HTML formatting.
        """
        message = (
            f"🎫 <b>Booking Confirmed!</b>\n\n"
            f"PNR: <code>{pnr}</code>\n"
            f"Train: {train_no}\n"
            f"ID: {booking_id}\n\n"
            f"<i>You can now download your ticket or check status below.</i>"
        )
        
        # Task 33.3 & 33.4: Inline buttons
        reply_markup = {
            "inline_keyboard": [[
                {"text": "📥 Download PDF", "callback_data": f"pdf_{booking_id}"},
                {"text": "🔍 Check Status", "callback_data": f"pnr_{pnr}"}
            ]]
        }
        
        return await self._api_request("sendMessage", {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        })

    async def send_ticket_pdf(self, chat_id: Union[str, int], pdf_path: str, caption: str = "Your E-Ticket"):
        """Task 33.3: Direct PDF download button / file delivery."""
        if not os.path.exists(pdf_path):
            logger.error(f"PDF not found for Telegram delivery: {pdf_path}")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                with open(pdf_path, "rb") as f:
                    files = {"document": (os.path.basename(pdf_path), f, "application/pdf")}
                    res = await client.post(
                        f"{self.base_url}/sendDocument",
                        data={"chat_id": chat_id, "caption": caption},
                        files=files,
                        timeout=30.0
                    )
                res.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Telegram PDF delivery failed: {e}")
            return False

    async def send_welcome(self, chat_id: Union[str, int]):
        """Task 33.6: Welcome message with suggestion buttons (RouteMaster Style)."""
        welcome = (
            "🚀 <b>RouteMaster / Rail Assistant Online</b>\n\n"
            "Systems operational. I am your advanced AI travel companion.\n\n"
            "How can I assist you with your logistics today?"
        )
        
        # Task 3.2: Mirroring web chatbot "Button Pattern" for Telegram
        reply_markup = self.get_keyboard("default")
        
        return await self._api_request("sendMessage", {
            "chat_id": chat_id,
            "text": welcome,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        })

    def get_keyboard(self, context: str = "default") -> Dict[str, Any]:
        """Task 3.2: Unified Keyboard Mirroring logic."""
        if context == "journey":
            buttons = [
                [{"text": "📍 Share Location"}, {"text": "🛡️ Safety Status"}],
                [{"text": "📊 Dashboard"}, {"text": "🚨 SOS Emergency"}]
            ]
        elif context == "search":
            buttons = [
                [{"text": "🔍 Check Availability"}, {"text": "🛤️ Alt Routes"}],
                [{"text": "📊 Dashboard"}, {"text": "🎫 Book Ticket"}]
            ]
        else:
            buttons = [
                [{"text": "🎫 Book Ticket"}, {"text": "🔍 Search Trains"}],
                [{"text": "📊 Dashboard"}, {"text": "📜 My Bookings"}],
                [{"text": "🚨 SOS Emergency"}, {"text": "❓ Help"}]
            ]
            
        return {
            "keyboard": buttons,
            "resize_keyboard": True,
            "one_time_keyboard": False
        }

    async def _api_request(self, method: str, payload: Dict[str, Any]):
        """Internal helper for Telegram API calls."""
        if not self.bot_token:
            logger.warning("TELEGRAM_TOKEN not configured. Message skipped.")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(f"{self.base_url}/{method}", json=payload, timeout=10.0)
                res.raise_for_status()
                return True
        except Exception as e:
            # Task 33.7: Offline Queuing (simulated here via error logging)
            logger.error(f"Telegram API {method} failed: {e}")
            return False

import os
telegram_dispatcher = TelegramDispatcher()
