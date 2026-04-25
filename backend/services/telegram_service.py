import httpx
import logging
from typing import Optional, List, Union
from datetime import datetime, timedelta
from database.config import Config
from core.resilience import circuit_breaker_manager
from core.retry import retry_async

logger = logging.getLogger(__name__)

class TelegramService:
    """
    Handles emergency broadcasts and notifications via Telegram Bot API.
    With circuit breaker protection and retry logic.
    """
    
    def __init__(self):
        self.bot_token = Config.TELEGRAM_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limit_window = timedelta(minutes=1)
        self._rate_limit_max = 30  # messages per window
        self._message_history: List[datetime] = []

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create shared HTTP client for connection reuse."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=30.0)
            )
        return self._client

    async def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = datetime.now()
        # Remove messages older than the window
        self._message_history = [
            ts for ts in self._message_history 
            if now - ts < self._rate_limit_window
        ]
        return len(self._message_history) < self._rate_limit_max

    async def _send_with_retry(
        self, 
        chat_id: Union[str, int], 
        text: str, 
        parse_mode: str = "Markdown",
        max_retries: int = 2
    ) -> bool:
        """Send message with retry logic."""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                client = self._get_client()
                res = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": parse_mode
                    },
                    timeout=10.0
                )
                res.raise_for_status()
                return True
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"Telegram timeout (attempt {attempt + 1}): {e}")
            except httpx.HTTPStatusError as e:
                last_error = e
                # Don't retry on client errors (4xx)
                if e.response.status_code < 500:
                    logger.error(f"Telegram client error: {e.response.status_code}")
                    return False
                logger.warning(f"Telegram server error (attempt {attempt + 1}): {e}")
            except Exception as e:
                last_error = e
                logger.error(f"Telegram send error (attempt {attempt + 1}): {e}")
        
        logger.error(f"Telegram send failed after {max_retries + 1} attempts: {last_error}")
        return False

    @circuit_breaker_manager.get_breaker("telegram").decorate
    async def send_message(self, chat_id: Union[str, int], text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message to a Telegram chat with resilience patterns.
        
        Args:
            chat_id: The Telegram chat ID
            text: Message text
            parse_mode: Text formatting mode (Markdown, HTML, etc.)
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured. Skipping message.")
            return False
        
        # Check rate limit
        if not await self._check_rate_limit():
            logger.warning("Telegram rate limit exceeded")
            return False
        
        # Send with retry
        success = await self._send_with_retry(chat_id, text, parse_mode)
        
        if success:
            self._message_history.append(datetime.now())
        
        return success

    async def broadcast_sos(
        self, 
        user_name: str, 
        lat: float, 
        lng: float, 
        telegram_ids: List[Union[str, int]],
        parallel: bool = True
    ) -> dict:
        """
        Sends an SOS alert to a list of Telegram IDs with resilience patterns.
        
        Args:
            user_name: Name of the passenger
            lat: Latitude of location
            lng: Longitude of location
            telegram_ids: List of Telegram chat IDs to notify
            parallel: Whether to send messages in parallel (default: True)
            
        Returns:
            dict with success count, failure count, and results
        """
        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        message = (
            f"🚨 *EMERGENCY SOS ALERT* 🚨\n\n"
            f"Passenger: *{user_name}*\n"
            f"Location: [{lat}, {lng}]({maps_url})\n\n"
            f"⚠️ Help is requested immediately. Click the link above to see the live location."
        )
        
        results = {
            "total": len(telegram_ids),
            "success": 0,
            "failed": 0,
            "details": []
        }
        
        if parallel:
            # Send all messages in parallel with semaphore limit
            import asyncio
            semaphore = asyncio.Semaphore(5)  # Limit concurrent sends
            
            async def send_with_limit(tid):
                async with semaphore:
                    success = await self.send_message(tid, message)
                    return tid, success
            
            tasks = [send_with_limit(tid) for tid in telegram_ids]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            
            for outcome in outcomes:
                if isinstance(outcome, Exception):
                    results["failed"] += 1
                    results["details"].append({"id": None, "error": str(outcome)})
                else:
                    tid, success = outcome
                    if success:
                        results["success"] += 1
                    else:
                        results["failed"] += 1
                    results["details"].append({"id": tid, "success": success})
        else:
            # Sequential send
            for tid in telegram_ids:
                success = await self.send_message(tid, message)
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                results["details"].append({"id": tid, "success": success})
        
        results["all_success"] = results["failed"] == 0
        return results

    async def close(self):
        """Close the HTTP client connection."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy" if self.bot_token else "misconfigured",
            "bot_configured": bool(self.bot_token),
            "rate_limit_available": len(self._message_history) < self._rate_limit_max,
            "circuit_breaker": circuit_breaker_manager.get_breaker("telegram").get_state()
        }

# Global instance
telegram_service = TelegramService()
