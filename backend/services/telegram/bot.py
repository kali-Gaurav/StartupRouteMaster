"""
Telegram Bot Dispatcher
Sends booking notifications and handles bot interactions.
"""

import httpx
import asyncio
import logging
import io
import time
from typing import Optional, List, Union, Dict, Any
from datetime import datetime
from collections import deque
from dataclasses import dataclass

from core.resilience.core import CircuitBreaker, CircuitConfig
from database.infrastructure.config import Config

logger = logging.getLogger("telegram.dispatcher")


class TelegramDispatcher:
    """Telegram bot dispatcher for booking notifications and interactions."""
    
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{Config._get_env('TELEGRAM_BOT_TOKEN')}"
        self._metrics_lock = asyncio.Lock()
        self._metrics: deque = deque(maxlen=1000)
        self._circuit_breaker = CircuitBreaker(
            "telegram_api",
            CircuitConfig(failure_threshold=5, timeout_seconds=60.0, success_threshold=2)
        )
        # Rate Limiting: Token Bucket (30 req/sec)
        self._rate_limit_lock = asyncio.Lock()
        self._tokens = 30.0
        self._last_refill = time.time()
        self._refill_rate = 30.0 # tokens per second
        
        logger.info("TelegramDispatcher initialized with Token Bucket Rate Limiting")

    async def _wait_for_token(self):
        """Ensures we stay within Telegram's rate limits."""
        async with self._rate_limit_lock:
            now = time.time()
            elapsed = now - self._last_refill
            self._tokens = min(30.0, self._tokens + elapsed * self._refill_rate)
            self._last_refill = now
            
            if self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self._refill_rate
                await asyncio.sleep(wait_time)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0

    async def _api_request(self, method: str, payload: dict) -> bool:
        """Helper to send requests to Telegram API with rate limiting and circuit breaking."""
        await self._wait_for_token()
        
        async def _call():
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/{method}",
                        json=payload,
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        return True
                    else:
                        logger.error(f"Telegram API {method} failed: {response.status_code} {response.text}")
                        raise Exception(f"HTTP {response.status_code}")
            except Exception as e:
                logger.error(f"Telegram API request failed: {e}")
                raise

        result = await self._circuit_breaker.execute(_call)
        return result if result is not None else False
    
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

    async def send_message(self, chat_id: Union[str, int], text: str, reply_markup: Optional[Dict] = None) -> bool:
        """Send generic text message."""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        return await self._api_request("sendMessage", payload)
    
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

    async def send_document(self, chat_id: Union[int, str], document_url: str, caption: str = "") -> bool:
        """Sends a document (e.g. Ticket PDF) to the user."""
        return await self._api_request("sendDocument", {
            "chat_id": chat_id,
            "document": document_url,
            "caption": caption,
            "parse_mode": "HTML"
        })

    async def send_photo(self, chat_id: Union[int, str], photo_url: str, caption: str = "") -> bool:
        """Sends a photo (e.g. Route Map) to the user."""
        return await self._api_request("sendPhoto", {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "HTML"
        })
    
    async def send_welcome(self, chat_id: Union[str, int]):
        """Send welcome message to new users."""
        welcome_message = """
<b>Welcome to RouteMaster! 🚂</b>

Your intelligent travel companion for safer and smarter journeys.

Available commands:
/search - Find multi-modal routes
/bookings - View recent bookings
/pnr - Check PNR status
/sos - Emergency help
/dashboard - Open your web profile
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

PNR: <code>{booking_details.get('pnr', 'N/A')}</code>
Train: {booking_details.get('train_name', 'N/A')}
From: {booking_details.get('from', 'N/A')}
To: {booking_details.get('to', 'N/A')}
Date: {booking_details.get('date', 'N/A')}
        """

    def get_keyboard(self, context: str = "default") -> Dict[str, Any]:
        """Returns standard keyboards based on context."""
        if context == "default":
            return {
                "inline_keyboard": [
                    [{"text": "🔍 Search Trains", "callback_data": "search_trains"}],
                    [{"text": "🎫 Book a Trip", "callback_data": "book_trip"}, {"text": "📋 My Bookings", "callback_data": "my_bookings"}],
                    [{"text": "🎫 Ticket / PNR", "callback_data": "ticket"}, {"text": "🚨 SOS", "callback_data": "sos"}],
                    [{"text": "📊 Dashboard", "callback_data": "dashboard"}, {"text": "❓ Help", "callback_data": "help"}]
                ]
            }
        elif context == "journey":
            return {
                "inline_keyboard": [
                    [{"text": "📍 Track Live Status", "callback_data": "track"}],
                    [{"text": "👂 Report Crowd", "callback_data": "crowd_feedback:start"}],
                    [{"text": "🚨 Emergency SOS", "callback_data": "sos"}]
                ]
            }
        elif context == "booking":
             return {
                "inline_keyboard": [
                    [{"text": "🌐 View on Website", "callback_data": "dashboard"}],
                    [{"text": "📍 Start Live Tracking", "callback_data": "track"}]
                ]
            }
        return {}

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._circuit_breaker.reset()
        logger.info("Circuit breaker reset for telegram dispatcher")


# Global instance
telegram_dispatcher = TelegramDispatcher()
