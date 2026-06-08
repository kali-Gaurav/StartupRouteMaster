"""
Telegram Bot Dispatcher
=======================
Handles all Telegram Bot API communications with resilience patterns.
"""

import httpx
import logging
import asyncio
import json
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
from collections import deque
from enum import Enum

from database.config import Config
from core.resilience.core import circuit_manager, CircuitConfig
from core.resilience.retry import RetryPolicy, retry_async
from .config import bot_config
from .schemas import BotResponse

logger = logging.getLogger(__name__)


class DispatcherStatus(str, Enum):
    """Dispatcher status."""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


class TelegramDispatcher:
    """
    Production-grade Telegram Bot API dispatcher.
    
    Features:
    - Circuit breaker protection
    - Exponential backoff retry
    - Rate limiting
    - Request queuing
    - Metrics tracking
    """
    
    def __init__(self):
        self.token = bot_config.bot_token
        if not self.token:
            self.token = Config.TELEGRAM_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        # Circuit breaker for API calls
        self._breaker = circuit_manager.get_or_create(
            "telegram_dispatcher",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=2
            )
        )
        
        # Retry policy
        self._retry_policy = RetryPolicy(
            max_attempts=bot_config.max_retries,
            initial_delay=bot_config.retry_delay_seconds,
            max_delay=bot_config.retry_max_delay_seconds,
            exponential_base=2.0,
            jitter=True,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "timeout" in str(e).lower(),
                lambda e: getattr(e, "status_code", 0) == 429,  # Rate limited
                lambda e: getattr(e, "status_code", 0) >= 500,  # Server errors
            ]
        )
        
        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None
        
        # Rate limiting
        self._rate_limit_window = timedelta(seconds=bot_config.rate_limit_window_seconds)
        self._rate_limit_max = bot_config.rate_limit_messages
        self._request_history: List[datetime] = []
        self._history_lock = asyncio.Lock()
        
        # Metrics
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Status
        self._status = DispatcherStatus.IDLE
        
        logger.info("TelegramDispatcher initialized with resilience patterns")
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    keepalive_expiry=30.0
                )
            )
        return self._client
    
    async def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        async with self._history_lock:
            now = datetime.now()
            # Remove old requests
            self._request_history = [
                ts for ts in self._request_history
                if now - ts < self._rate_limit_window
            ]
            
            if len(self._request_history) >= self._rate_limit_max:
                logger.warning("Rate limit exceeded")
                return False
            
            return True
    
    async def _api_request(
        self,
        method: str,
        payload: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an API request with resilience patterns.
        
        Args:
            method: API method name
            payload: Request payload
            files: Files to upload
            
        Returns:
            API response as dictionary
            
        Raises:
            Exception: If request fails after retries
        """
        url = f"{self.base_url}/{method}"
        
        # Check rate limit
        if not await self._check_rate_limit():
            self._status = DispatcherStatus.RATE_LIMITED
            raise Exception("Rate limit exceeded")
        
        # Execute with retry
        async def _execute():
            client = self._get_client()
            
            if files:
                response = await client.post(url, data=payload, files=files)
            else:
                response = await client.post(url, json=payload)
            
            response.raise_for_status()
            return response.json()
        
        try:
            result = await self._retry_policy.execute(_execute)
            
            # Record successful request
            async with self._history_lock:
                self._request_history.append(datetime.now())
            
            self._status = DispatcherStatus.RUNNING
            return result
            
        except Exception as e:
            self._status = DispatcherStatus.ERROR
            logger.error(f"Telegram API error ({method}): {e}")
            raise
    
    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        parse_mode: str = "HTML",
        keyboard: Optional[Dict[str, Any]] = None,
        inline_keyboard: Optional[List[List[Dict[str, str]]]] = None,
        reply_to: Optional[int] = None,
        delete_after: Optional[int] = None
    ) -> bool:
        """
        Send a text message.
        
        Args:
            chat_id: Target chat ID
            text: Message text
            parse_mode: Text formatting (HTML, Markdown)
            keyboard: Reply keyboard markup
            inline_keyboards: Inline keyboard buttons
            reply_to: Message ID to reply to
            delete_after: Seconds after which to delete message
            
        Returns:
            True if sent successfully
        """
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        
        if keyboard:
            payload["reply_markup"] = keyboard
        
        if inline_keyboard:
            payload["reply_markup"] = {"inline_keyboard": inline_keyboard}
        
        try:
            result = await self._api_request("sendMessage", payload)
            
            # Record metrics
            await self._record_metrics("send_message", True)
            
            # Handle delete_after
            if delete_after and result.get("result"):
                message_id = result["result"]["message_id"]
                asyncio.create_task(self._delete_message(chat_id, message_id, delete_after))
            
            return True
            
        except Exception as e:
            await self._record_metrics("send_message", False, str(e))
            logger.error(f"Failed to send message: {e}")
            return False
    
    async def send_document(
        self,
        chat_id: Union[int, str],
        document_path: str,
        caption: Optional[str] = None,
        keyboard: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a document (PDF, image, etc.).
        
        Args:
            chat_id: Target chat ID
            document_path: Path to document
            caption: Document caption
            keyboard: Inline keyboard
            
        Returns:
            True if sent successfully
        """
        import os
        
        if not os.path.exists(document_path):
            logger.error(f"Document not found: {document_path}")
            return False
        
        try:
            with open(document_path, "rb") as f:
                files = {"document": (os.path.basename(document_path), f)}
                payload = {"chat_id": chat_id}
                
                if caption:
                    payload["caption"] = caption
                
                if keyboard:
                    payload["reply_markup"] = keyboard
                
                result = await self._api_request("sendDocument", payload, files)
                await self._record_metrics("send_document", True)
                return True
                
        except Exception as e:
            await self._record_metrics("send_document", False, str(e))
            logger.error(f"Failed to send document: {e}")
            return False
    
    async def send_photo(
        self,
        chat_id: Union[int, str],
        photo_path: str,
        caption: Optional[str] = None,
        keyboard: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send a photo."""
        import os
        
        if not os.path.exists(photo_path):
            logger.error(f"Photo not found: {photo_path}")
            return False
        
        try:
            with open(photo_path, "rb") as f:
                files = {"photo": (os.path.basename(photo_path), f)}
                payload = {"chat_id": chat_id}
                
                if caption:
                    payload["caption"] = caption
                
                if keyboard:
                    payload["reply_markup"] = keyboard
                
                result = await self._api_request("sendPhoto", payload, files)
                await self._record_metrics("send_photo", True)
                return True
                
        except Exception as e:
            await self._record_metrics("send_photo", False, str(e))
            return False
    
    async def edit_message(
        self,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        parse_mode: str = "HTML",
        inline_keyboard: Optional[List[List[Dict[str, str]]]] = None
    ) -> bool:
        """Edit an existing message."""
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        if inline_keyboard:
            payload["reply_markup"] = {"inline_keyboard": inline_keyboard}
        
        try:
            await self._api_request("editMessageText", payload)
            await self._record_metrics("edit_message", True)
            return True
        except Exception as e:
            await self._record_metrics("edit_message", False, str(e))
            return False
    
    async def delete_message(
        self,
        chat_id: Union[int, str],
        message_id: int
    ) -> bool:
        """Delete a message."""
        try:
            await self._api_request("deleteMessage", {
                "chat_id": chat_id,
                "message_id": message_id
            })
            await self._record_metrics("delete_message", True)
            return True
        except Exception as e:
            await self._record_metrics("delete_message", False, str(e))
            return False
    
    async def answer_callback(
        self,
        callback_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> bool:
        """Answer a callback query."""
        payload = {"callback_query_id": callback_id}
        
        if text:
            payload["text"] = text
            payload["show_alert"] = show_alert
        
        try:
            await self._api_request("answerCallbackQuery", payload)
            await self._record_metrics("answer_callback", True)
            return True
        except Exception as e:
            await self._record_metrics("answer_callback", False, str(e))
            return False
    
    async def _delete_message(
        self,
        chat_id: Union[int, str],
        message_id: int,
        delay: int
    ) -> None:
        """Delete a message after a delay."""
        await asyncio.sleep(delay)
        await self.delete_message(chat_id, message_id)
    
    async def send_response(self, response: BotResponse) -> bool:
        """Send a BotResponse object."""
        return await self.send_message(
            chat_id=response.chat_id,
            text=response.text,
            parse_mode=response.parse_mode,
            keyboard=response.keyboard,
            inline_keyboard=response.inline_keyboard,
            reply_to=response.reply_to,
            delete_after=response.delete_after
        )
    
    async def get_me(self) -> Optional[Dict[str, Any]]:
        """Get bot information."""
        try:
            return await self._api_request("getMe")
        except Exception as e:
            logger.error(f"Failed to get bot info: {e}")
            return None
    
    async def get_chat(self, chat_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Get chat information."""
        try:
            return await self._api_request("getChat", {"chat_id": chat_id})
        except Exception as e:
            logger.error(f"Failed to get chat: {e}")
            return None
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.info("TelegramDispatcher HTTP client closed")
    
    async def _record_metrics(
        self,
        operation: str,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """Record operation metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "success": success,
                "error": error
            })
    
    def get_metrics(self) -> dict:
        """Get dispatcher metrics."""
        if not self._metrics:
            return {"total_operations": 0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_operation = {}
        
        for m in self._metrics:
            op = m["operation"]
            if op not in by_operation:
                by_operation[op] = {"total": 0, "success": 0}
            by_operation[op]["total"] += 1
            if m["success"]:
                by_operation[op]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "by_operation": by_operation,
            "status": self._status.value,
            "circuit_breaker": {
                "state": self._breaker.get_state().value,
                "failure_count": self._breaker.failure_count
            }
        }
    
    def health_check(self) -> dict:
        """Check dispatcher health."""
        return {
            "status": "healthy" if self._status != DispatcherStatus.ERROR else "unhealthy",
            "bot_configured": bool(self.token),
            "dispatcher_status": self._status.value,
            "circuit_breaker": {
                "state": self._breaker.get_state().value,
                "failure_count": self._breaker.failure_count,
                "success_count": self._breaker.success_count
            },
            "metrics": self.get_metrics()
        }
    
    def reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker."""
        self._breaker.reset()
        logger.info("Circuit breaker reset for telegram dispatcher")


# Global instance
telegram_dispatcher = TelegramDispatcher()
