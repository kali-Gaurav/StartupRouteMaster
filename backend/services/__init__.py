"""
Services Package
================

RouteMaster backend services for travel planning, booking, and chatbot functionality.

Modules:
- travel_planning_api: Travel planning API endpoints
- telegram_dispatcher: Telegram bot notifications
- conversation_manager: Multi-turn conversation handling
- interactive_bot_handler: Interactive chatbot with rich responses
- telegram_interactive_handler: Telegram-specific interactive handler
- interactive_response_types: Rich response type definitions
- interactive_bot_api: API endpoints for the interactive bot
- demo_interactive_chatbot: Demo script for the chatbot

Author: RouteMaster Team
Version: 1.0.0
"""

from .travel_planning_api import router as travel_planning_router
from .telegram_dispatcher import telegram_dispatcher
from .conversation_manager import (
    ConversationManager,
    ConversationContext,
    ConversationState,
    Intent,
    Entity,
    conversation_manager
)
from .interactive_bot_handler import (
    InteractiveBotHandler,
    InteractiveResponse,
    ActionType,
    ResponseType,
    Platform,
    interactive_bot_handler
)
from .interactive_response_types import (
    InteractiveResponseBuilder,
    Button,
    FormField,
    CarouselItem,
    create_search_results,
    create_booking_confirmation,
    create_pnr_status,
    create_train_tracking
)
from .telegram_interactive_handler import (
    TelegramInteractiveHandler,
    TelegramUpdate,
    telegram_interactive_handler
)
from api.interactive_bot_api import router as interactive_bot_router

__all__ = [
    # Travel Planning
    'travel_planning_router',
    
    # Telegram
    'telegram_dispatcher',
    
    # Conversation Management
    'ConversationManager',
    'ConversationContext',
    'ConversationState',
    'Intent',
    'Entity',
    'conversation_manager',
    
    # Interactive Bot
    'InteractiveBotHandler',
    'InteractiveResponse',
    'ActionType',
    'ResponseType',
    'Platform',
    'interactive_bot_handler',
    
    # Response Types
    'InteractiveResponseBuilder',
    'Button',
    'FormField',
    'CarouselItem',
    'create_search_results',
    'create_booking_confirmation',
    'create_pnr_status',
    'create_train_tracking',
    
    # Telegram Handler
    'TelegramInteractiveHandler',
    'TelegramUpdate',
    'telegram_interactive_handler',
    
    # API
    'interactive_bot_router'
]