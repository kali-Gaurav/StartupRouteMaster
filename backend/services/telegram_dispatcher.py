"""
Telegram Bot Dispatcher
Sends booking notifications and handles bot interactions.
"""

import httpx
import asyncio
import logging
import io
from typing import Optional, List, Union, Dict, Any
from datetime import datetime
from collections import deque
from dataclasses import dataclass

from core.resilience import CircuitBreaker, CircuitConfig
from database.config import Config

logger = logging.getLogger("telegram.dispatcher")


class TelegramDispatcher:
    """Telegram bot dispatcher for booking notifications and interactions."""
    
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}"
        self._metrics_lock = asyncio.Lock()
        self._metrics: deque = deque(maxlen=1000)
        self._circuit_breaker = CircuitBreaker(
            "telegram_api",
            CircuitConfig(failure_threshold=5, timeout_seconds=60.0, success_threshold=2)
        )
        logger.info("TelegramDispatcher initialized with resilience patterns")
    
    async def send_booking_notification(self, chat_id: Union[str, int], booking_details: Dict) -> bool:
        """Send booking confirmation notification."""
        try:
            message = self._format_booking_message(booking_details)
            keyboard = self.get_keyboard("booking")
            return await self._api_request("sendMessage", {
                "chat_id": chat_id,
                "text": message,
                "reply_markup": keyboard,
                "parse_mode": "HTML"
            })
        except Exception as e:
            logger.error(f"Failed to send booking notification: {e}")
            return False
    
    async def send_ticket_pdf(self, chat_id: Union[str, int], pdf_path: str, caption: str = "Your Ticket"):
        """Send ticket PDF to user."""
        try:
            with open(pdf_path, 'rb') as pdf:
                files = {'document': pdf}
                data = {'chat_id': chat_id, 'caption': caption}
                async with httpx.AsyncClient() as client:
                    res = await client.post(
                        f"{self.base_url}/sendDocument",
                        files=files,
                        data=data,
                        timeout=30.0
                    )
                    return res.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send ticket PDF: {e}")
            return False
    
    async def send_welcome(self, chat_id: Union[str, int]):
        """Send welcome message to new users."""
        welcome_message = """
<b>Welcome to RailMate! 🚂</b>

Your intelligent travel companion for Indian Railways.

Available commands:
/search - Find train routes
/book - Make a new booking
/status - Check PNR status
/cancel - Cancel booking
/help - Get help

How can I help you today?
        """
        return await self._api_request("sendMessage", {
            "chat_id": chat_id,
            "text": welcome_message,
            "parse_mode": "HTML",
            "reply_markup": self.get_keyboard("default")
        })
    
    def _format_booking_message(self, booking_details: Dict) -> str:
        """Format booking details for message."""
        return f"""
<b>Booking Confirmed! 🎫</b>

PNR: {booking_details.get('pnr', 'N/A')}
Train: {booking_details.get('train_name', 'N/A')}
From: {booking_details.get('from', 'N/A')}
To: {booking_details.get('to', 'N/A')}
Date: {booking_details.get('date', 'N/A')}
Class: {booking_details.get('class', 'N/A')}
Seats: {booking_details.get('seats', 'N/A')}

Have a safe journey! 🚂
        """
    
    def get_keyboard(self, context: str = "default") -> Dict[str, Any]:
        """Get inline keyboard based on context."""
        keyboards = {
            "default": {
                "inline_keyboard": [
                    [{"text": "🔍 Search Trains", "callback_data": "search_trains"}],
                    [{"text": "🎫 My Bookings", "callback_data": "my_bookings"}],
                    [{"text": "📊 Dashboard", "callback_data": "dashboard"}],
                    [{"text": "❓ Help", "callback_data": "help"}]
                ]
            },
            "booking": {
                "inline_keyboard": [
                    [{"text": "✅ Confirm", "callback_data": "confirm_booking"}],
                    [{"text": "❌ Cancel", "callback_data": "cancel_booking"}],
                    [{"text": "🔙 Back", "callback_data": "back"}]
                ]
            },
            "journey": {
                "inline_keyboard": [
                    [{"text": "📍 Live Status", "callback_data": "track"}],
                    [{"text": "🆘 SOS", "callback_data": "sos"}],
                    [{"text": "📊 Dashboard", "callback_data": "dashboard"}]
                ]
            },
            "help": {
                "inline_keyboard": [
                    [{"text": "🔍 Search Trains", "callback_data": "search_trains"}],
                    [{"text": "🎫 My Bookings", "callback_data": "my_bookings"}],
                    [{"text": "🆘 SOS", "callback_data": "sos"}]
                ]
            }
        }
        return keyboards.get(context, keyboards["default"])
    
    async def send_message(
        self,
        chat_id: Union[str, int],
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
        disable_web_page_preview: bool = True
    ) -> bool:
        """Send a generic message to Telegram."""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._api_request("sendMessage", payload)

    async def _api_request(self, method: str, payload: Dict[str, Any]) -> bool:
        """Make API request with circuit breaker."""
        try:
            async with self._circuit_breaker:
                async with httpx.AsyncClient() as client:
                    res = await client.post(f"{self.base_url}/{method}", json=payload, timeout=10.0)
                    res.raise_for_status()
                    await self._record_metrics(method, True)
                    return True
        except Exception as e:
            logger.error(f"Telegram API {method} failed: {e}")
            await self._record_metrics(method, False, error=str(e))
            return False
    
    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================
    
    async def _record_metrics(self, operation_type: str, success: bool, error: str = ""):
        """Record operation metrics."""
        # Ensure error is always a string
        if error is None:
            error = ""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "error": error
            })
    
    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0
        }
    
    def health_check(self) -> dict:
        """Health check for the dispatcher."""
        cb = self._circuit_breaker
        # Use .state or .get_state() for circuit breaker state
        cb_state = cb.state.value if hasattr(cb, 'state') and cb.state else (cb.get_state().value if hasattr(cb, 'get_state') else str(cb))
        return {
            "status": "healthy",
            "circuit_breaker": cb_state
        }
    
    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._circuit_breaker.reset()
        logger.info("Circuit breaker reset for telegram dispatcher")


# Global instance
telegram_dispatcher = TelegramDispatcher()