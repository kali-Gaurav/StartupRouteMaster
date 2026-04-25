"""
Main Telegram Bot
=================
Production-grade Telegram bot with full feature set.
"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from telegram_bot.schemas import (
    TelegramMessage, TelegramUpdate, CallbackQuery,
    IntentType, UserState, BotResponse
)
from telegram_bot.dispatcher import TelegramDispatcher, telegram_dispatcher
from telegram_bot.command_router import CommandRouter, command_router
from telegram_bot.handlers import (
    StartHandler, SearchHandler, BookingHandler,
    PNRHandler, ProfileHandler, SOSHandler, HelpHandler
)
from telegram_bot.user_session_manager import user_session_manager
from telegram_bot.config import bot_config

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Production-grade Telegram Bot.
    
    Features:
    - Full command handling
    - Natural language processing
    - Multi-step workflows
    - Context-aware conversations
    - SOS emergency handling
    - Full website integration
    """
    
    def __init__(self):
        self.dispatcher = telegram_dispatcher
        self.router = command_router
        self._running = False
        
        # Initialize handlers
        self._init_handlers()
        
        # Register routes
        self._register_routes()
        
        logger.info("TelegramBot initialized")
    
    def _init_handlers(self):
        """Initialize command handlers."""
        self.start_handler = StartHandler()
        self.search_handler = SearchHandler()
        self.booking_handler = BookingHandler()
        self.pnr_handler = PNRHandler()
        self.profile_handler = ProfileHandler()
        self.sos_handler = SOSHandler()
        self.help_handler = HelpHandler()
    
    def _register_routes(self):
        """Register command routes with router."""
        # Core commands
        self.router.register_handler(IntentType.START, self._handle_start)
        self.router.register_handler(IntentType.MAIN_MENU, self._handle_main_menu)
        
        # Search & booking
        self.router.register_handler(IntentType.SEARCH_TRAINS, self._handle_search)
        self.router.register_handler(IntentType.BOOK_TICKET, self._handle_booking)
        self.router.register_handler(IntentType.CHECK_AVAILABILITY, self._handle_availability)
        
        # PNR & bookings
        self.router.register_handler(IntentType.CHECK_PNR, self._handle_pnr)
        self.router.register_handler(IntentType.VIEW_BOOKINGS, self._handle_bookings)
        self.router.register_handler(IntentType.CANCEL_BOOKING, self._handle_cancellation)
        self.router.register_handler(IntentType.DOWNLOAD_TICKET, self._handle_download)
        
        # User management
        self.router.register_handler(IntentType.MY_PROFILE, self._handle_profile)
        self.router.register_handler(IntentType.MY_WALLET, self._handle_wallet)
        
        # Help & support
        self.router.register_handler(IntentType.HELP, self._handle_help)
        self.router.register_handler(IntentType.SUPPORT, self._handle_support)
        
        # SOS & safety
        self.router.register_handler(IntentType.SOS_EMERGENCY, self._handle_sos)
        self.router.register_handler(IntentType.SAFETY_STATUS, self._handle_safety)
        
        # Navigation
        self.router.register_handler(IntentType.BACK, self._handle_back)
        self.router.register_handler(IntentType.UNKNOWN, self._handle_unknown)
        
        # Fallback
        self.router.register_fallback(self._handle_unknown)
    
    # Handler methods
    async def _handle_start(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.start_handler.handle(message, context, intent_result)
    
    async def _handle_main_menu(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        from telegram_bot.keyboards import keyboard_builder
        return type('Result', (), {
            'status': type('Status', (), {'SUCCESS: 'success'})(),
            'response': BotResponse(
                chat_id=message.chat.id,
                text="🏠 <b>Main Menu</b>\n\nHow can I help you today?",
                keyboard=keyboard_builder.main_menu()
            ),
            'next_state': 'idle',
            'data': {}
        })()
    
    async def _handle_search(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.search_handler.handle(message, context, intent_result)
    
    async def _handle_booking(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.booking_handler.handle(message, context, intent_result)
    
    async def _handle_availability(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.search_handler.handle(message, context, intent_result)
    
    async def _handle_pnr(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.pnr_handler.handle(message, context, intent_result)
    
    async def _handle_bookings(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.pnr_handler.handle(message, context, intent_result)
    
    async def _handle_cancellation(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.pnr_handler.handle(message, context, intent_result)
    
    async def _handle_download(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.pnr_handler.handle(message, context, intent_result)
    
    async def _handle_profile(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.profile_handler.handle(message, context, intent_result)
    
    async def _handle_wallet(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.profile_handler.handle(message, context, intent_result)
    
    async def _handle_help(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.help_handler.handle(message, context, intent_result)
    
    async def _handle_support(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.help_handler.handle(message, context, intent_result)
    
    async def _handle_sos(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.sos_handler.handle(message, context, intent_result)
    
    async def _handle_safety(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        return await self.sos_handler.handle(message, context, intent_result)
    
    async def _handle_back(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        from telegram_bot.keyboards import keyboard_builder
        return type('Result', (), {
            'status': type('Status', (), {'SUCCESS: 'success'})(),
            'response': BotResponse(
                chat_id=message.chat.id,
                text="🔙 <b>Back</b>\n\nWhat would you like to do?",
                keyboard=keyboard_builder.main_menu()
            ),
            'next_state': 'idle',
            'data': {}
        })()
    
    async def _handle_unknown(
        self,
        message: TelegramMessage,
        context,
        intent_result
    ):
        from telegram_bot.keyboards import keyboard_builder
        return type('Result', (), {
            'status': type('Status', (), {'FAILED: 'failed'})(),
            'response': BotResponse(
                chat_id=message.chat.id,
                text=intent_result.suggested_response or "I didn't understand that. Please try again or use the menu below.",
                keyboard=keyboard_builder.main_menu()
            ),
            'next_state': 'idle',
            'data': {}
        })()
    
    # Main processing methods
    async def process_update(self, update: Dict[str, Any]) -> Optional[BotResponse]:
        """
        Process a Telegram update.
        
        Args:
            update: Raw Telegram update dictionary
            
        Returns:
            BotResponse or None
        """
        try:
            # Parse update
            telegram_update = self._parse_update(update)
            if not telegram_update:
                return None
            
            # Route based on update type
            if telegram_update.message:
                return await self._process_message(telegram_update.message)
            elif telegram_update.callback_query:
                return await self._process_callback(telegram_update.callback_query)
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing update: {e}", exc_info=True)
            return None
    
    def _parse_update(self, update: Dict[str, Any]) -> Optional[TelegramUpdate]:
        """Parse raw update into TelegramUpdate."""
        try:
            update_id = update.get("update_id", 0)
            
            if "message" in update:
                message = self._parse_message(update["message"])
                return TelegramUpdate(
                    update_id=update_id,
                    update_type="message",
                    message=message
                )
            elif "callback_query" in update:
                callback = self._parse_callback(update["callback_query"])
                return TelegramUpdate(
                    update_id=update_id,
                    update_type="callback_query",
                    callback_query=callback
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing update: {e}")
            return None
    
    def _parse_message(self, msg: Dict[str, Any]) -> TelegramMessage:
        """Parse message data."""
        from_user = None
        if "from" in msg:
            from_user = type('User', (), {
                'id': msg["from"].get("id", 0),
                'is_bot': msg["from"].get("is_bot", False),
                'first_name': msg["from"].get("first_name", ""),
                'last_name': msg["from"].get("last_name"),
                'username': msg["from"].get("username"),
                'language_code': msg["from"].get("language_code")
            })()
        
        chat = type('Chat', (), {
            'id': msg["chat"].get("id", 0),
            'type': msg["chat"].get("type", "private"),
            'title': msg["chat"].get("title"),
            'username': msg["chat"].get("username"),
            'first_name': msg["chat"].get("first_name"),
            'last_name': msg["chat"].get("last_name")
        })()
        
        # Determine message type
        message_type = "text"
        if "text" in msg:
            message_type = "text"
        elif "photo" in msg:
            message_type = "photo"
        elif "document" in msg:
            message_type = "document"
        elif "location" in msg:
            message_type = "location"
        elif "contact" in msg:
            message_type = "contact"
        
        return TelegramMessage(
            message_id=msg.get("message_id", 0),
            from_user=from_user,
            chat=chat,
            date=datetime.fromtimestamp(msg.get("date", 0)),
            text=msg.get("text", ""),
            message_type=message_type,
            location=msg.get("location"),
            contact=msg.get("contact"),
            reply_to_message=self._parse_message(msg["reply_to_message"]) if msg.get("reply_to_message") else None
        )
    
    def _parse_callback(self, callback: Dict[str, Any]) -> CallbackQuery:
        """Parse callback query."""
        from_user = type('User', (), {
            'id': callback["from"].get("id", 0),
            'is_bot': callback["from"].get("is_bot", False),
            'first_name': callback["from"].get("first_name", ""),
            'last_name': callback["from"].get("last_name"),
            'username': callback["from"].get("username"),
            'language_code': callback["from"].get("language_code")
        })()
        
        message = None
        if callback.get("message"):
            message = self._parse_message(callback["message"])
        
        return CallbackQuery(
            id=callback.get("id", ""),
            from_user=from_user,
            message=message,
            data=callback.get("data", "")
        )
    
    async def _process_message(self, message: TelegramMessage) -> Optional[BotResponse]:
        """Process incoming message."""
        try:
            chat_id = message.chat.id
            user_id = message.from_user.id if message.from_user else 0
            
            # Log message
            logger.debug(f"Processing message from {user_id} in chat {chat_id}: {message.text[:50]}...")
            
            # Route message
            response = await self.router.route(
                message=message,
                chat_id=chat_id,
                user_id=user_id
            )
            
            # Send response if exists
            if response:
                await self.dispatcher.send_response(response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return None
    
    async def _process_callback(self, callback: CallbackQuery) -> Optional[BotResponse]:
        """Process callback query."""
        try:
            chat_id = callback.message.chat.id if callback.message else 0
            user_id = callback.from_user.id
            data = callback.data
            
            # Answer callback first
            await self.dispatcher.answer_callback(callback.id)
            
            # Parse callback data
            action = data.split("_")[0] if "_" in data else data
            
            # Route to appropriate handler
            handlers = {
                "search": self.search_handler,
                "book": self.booking_handler,
                "pnr": self.pnr_handler,
                "booking": self.pnr_handler,
                "pdf": self.pnr_handler,
                "cancel": self.pnr_handler,
                "profile": self.profile_handler,
                "wallet": self.profile_handler,
                "sos": self.sos_handler,
                "help": self.help_handler,
            }
            
            handler = handlers.get(action)
            if handler:
                # Get session
                session = await user_session_manager.get_session(chat_id, user_id)
                
                # Handle callback
                result = await handler.handle_callback(data, chat_id, session.context)
                
                if result.response:
                    await self.dispatcher.send_response(result.response)
                
                return result.response
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing callback: {e}", exc_info=True)
            return None
    
    # Bot lifecycle
    async def start(self) -> None:
        """Start the bot."""
        if self._running:
            logger.warning("Bot is already running")
            return
        
        self._running = True
        logger.info("TelegramBot started")
        
        # Verify bot connection
        bot_info = await self.dispatcher.get_me()
        if bot_info:
            logger.info(f"Bot connected: @{bot_info.get('result', {}).get('username', 'unknown')}")
        else:
            logger.error("Failed to connect to Telegram")
    
    async def stop(self) -> None:
        """Stop the bot."""
        self._running = False
        await self.dispatcher.close()
        logger.info("TelegramBot stopped")
    
    def is_running(self) -> bool:
        """Check if bot is running."""
        return self._running
    
    # Metrics and health
    def get_health(self) -> Dict[str, Any]:
        """Get bot health status."""
        return {
            "status": "running" if self._running else "stopped",
            "dispatcher": self.dispatcher.health_check(),
            "router": self.router.get_metrics()
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get bot metrics."""
        return {
            "router": self.router.get_metrics(),
            "dispatcher": self.dispatcher.get_metrics()
        }


# Global bot instance
telegram_bot = TelegramBot()