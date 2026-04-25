"""
Command Router
==============
Routes commands and intents to appropriate handlers.
"""

import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from collections import deque
import asyncio

from .schemas import (
    IntentType, UserContext, BotResponse, 
    TelegramMessage, CallbackQuery
)
from .intent_classifier import IntentClassifier, IntentResult
from .user_session_manager import UserSessionManager
from .config import bot_config

logger = logging.getLogger(__name__)


class HandlerResultStatus(str, Enum):
    """Handler result status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NEEDS_INPUT = "needs_input"
    RATE_LIMITED = "rate_limited"


@dataclass
class HandlerResult:
    """Result from a command handler."""
    status: HandlerResultStatus
    response: Optional[BotResponse] = None
    next_state: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    follow_up: bool = False
    follow_up_text: Optional[str] = None


class CommandRouter:
    """
    Routes incoming messages to appropriate handlers based on intent.
    Implements a pipeline: classify → route → execute → respond.
    """
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.session_manager = UserSessionManager()
        
        # Handler registry
        self._handlers: Dict[IntentType, Callable] = {}
        self._fallback_handler: Optional[Callable] = None
        
        # Middleware
        self._middleware: list = []
        
        # Metrics
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("CommandRouter initialized")
    
    def register_handler(
        self, 
        intent: IntentType, 
        handler: Callable[[TelegramMessage, UserContext, IntentResult], Awaitable[HandlerResult]]
    ) -> None:
        """Register a handler for an intent."""
        self._handlers[intent] = handler
        logger.debug(f"Registered handler for intent: {intent.value}")
    
    def register_fallback(
        self, 
        handler: Callable[[TelegramMessage, UserContext, IntentResult], Awaitable[HandlerResult]]
    ) -> None:
        """Register a fallback handler for unknown intents."""
        self._fallback_handler = handler
    
    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware to the processing pipeline."""
        self._middleware.append(middleware)
    
    async def route(
        self, 
        message: TelegramMessage,
        chat_id: int,
        user_id: int
    ) -> Optional[BotResponse]:
        """
        Route a message to the appropriate handler.
        
        Args:
            message: Incoming Telegram message
            chat_id: Chat ID for response
            user_id: User ID for context
            
        Returns:
            BotResponse or None
        """
        start_time = datetime.utcnow()
        
        try:
            # Get or create user session
            session = await self.session_manager.get_session(chat_id, user_id)
            
            # Run middleware
            for mw in self._middleware:
                await mw(message, session)
            
            # Classify intent
            intent_result = await self.intent_classifier(
                text=message.text or "",
                context=session.context,
                user_id=user_id
            )
            
            # Update session with intent
            session.context.intent = intent_result.intent
            session.context.updated_at = datetime.utcnow()
            
            # Get appropriate handler
            handler = self._handlers.get(
                intent_result.intent, 
                self._fallback_handler
            )
            
            if not handler:
                # Default fallback
                response = await self._default_fallback(
                    message, session, intent_result, chat_id
                )
                await self._record_metrics(
                    intent_result, start_time, HandlerResultStatus.FAILED
                )
                return response
            
            # Execute handler
            result = await handler(message, session.context, intent_result)
            
            # Update session state
            if result.next_state:
                session.context.state = result.next_state
            if result.data:
                session.context.data.update(result.data)
            
            # Save session
            await self.session_manager.save_session(session)
            
            # Record metrics
            await self._record_metrics(intent_result, start_time, result.status)
            
            return result.response
            
        except Exception as e:
            logger.error(f"Error routing message: {e}", exc_info=True)
            await self._record_metrics(
                IntentResult(
                    intent=IntentType.UNKNOWN,
                    confidence=0.0,
                    entities={},
                    raw_text=message.text or ""
                ),
                start_time,
                HandlerResultStatus.FAILED
            )
            return self._error_response(chat_id, str(e))
    
    async def route_callback(
        self,
        callback: CallbackQuery,
        chat_id: int,
        user_id: int
    ) -> Optional[BotResponse]:
        """Route a callback query from inline keyboard."""
        try:
            # Parse callback data
            action, value = self._parse_callback_data(callback.data)
            
            # Get session
            session = await self.session_manager.get_session(chat_id, user_id)
            
            # Route based on action
            handler = self._handlers.get(f"callback_{action}")
            if handler:
                result = await handler(callback, session.context, value)
                await self.session_manager.save_session(session)
                return result.response
            
            # Default callback handling
            return await self._default_callback(callback, session, chat_id)
            
        except Exception as e:
            logger.error(f"Error routing callback: {e}", exc_info=True)
            return self._error_response(chat_id, str(e))
    
    def _parse_callback_data(self, data: str) -> tuple:
        """Parse callback data into action and value."""
        if "_" in data:
            parts = data.split("_", 1)
            return parts[0], parts[1] if len(parts) > 1 else ""
        return data, ""
    
    async def _default_fallback(
        self,
        message: TelegramMessage,
        session,
        intent_result: IntentResult,
        chat_id: int
    ) -> BotResponse:
        """Default fallback for unknown intents."""
        return BotResponse(
            chat_id=chat_id,
            text=intent_result.suggested_response or "I didn't understand that. Please try again.",
            inline_keyboard=[
                [
                    {"text": "🔍 Search Trains", "callback_data": "search_trains"},
                    {"text": "🎫 My Bookings", "callback_data": "my_bookings"},
                ],
                [
                    {"text": "❓ Help", "callback_data": "help"},
                    {"text": "📊 Dashboard", "callback_data": "dashboard"},
                ]
            ]
        )
    
    async def _default_callback(
        self,
        callback: CallbackQuery,
        session,
        chat_id: int
    ) -> BotResponse:
        """Default callback handling."""
        return BotResponse(
            chat_id=chat_id,
            text="Processing your request...",
            parse_mode="HTML"
        )
    
    def _error_response(self, chat_id: int, error: str) -> BotResponse:
        """Generate error response."""
        return BotResponse(
            chat_id=chat_id,
            text=f"❌ <b>Error</b>\n\nAn error occurred: {error}\n\nPlease try again or contact support.",
            parse_mode="HTML"
        )
    
    async def _record_metrics(
        self,
        intent_result: IntentResult,
        start_time: datetime,
        status: HandlerResultStatus
    ) -> None:
        """Record routing metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": start_time,
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "status": status.value,
                "duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
            })
    
    def get_metrics(self) -> dict:
        """Get router metrics."""
        if not self._metrics:
            return {"total_routes": 0}
        
        total = len(self._metrics)
        by_status = {}
        by_intent = {}
        
        for m in self._metrics:
            status = m["status"]
            intent = m["intent"]
            
            by_status[status] = by_status.get(status, 0) + 1
            by_intent[intent] = by_intent.get(intent, 0) + 1
        
        return {
            "total_routes": total,
            "by_status": by_status,
            "by_intent": by_intent,
            "avg_duration_ms": sum(m["duration_ms"] for m in self._metrics) / total
        }


# Global instance
command_router = CommandRouter()