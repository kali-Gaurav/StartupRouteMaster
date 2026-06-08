"""
Services Package (Modularized)
==============================

RouteMaster backend services organized by logical domain.
This module exports the main service interfaces for the application.

Modules:
- planning: Travel planning and reconstruction
- telegram: Bot dispatching and interaction handling
- intelligence: NLP, conversation, and rich responses
- booking: PNR and reservation services
- finance: Payments and reconciliation
- pricing: Yield and price calculation
- security: Fraud and audit
- cache: Data caching and warming
"""

from .planning.api import router as travel_planning_router
from .telegram.bot import telegram_dispatcher
from .intelligence.conversation import (
    ConversationManager,
    ConversationContext,
    ConversationState,
    Intent,
    Entity,
    conversation_manager
)
from .intelligence.bot_handler import (
    InteractiveBotHandler,
    InteractiveResponse,
    ActionType,
    ResponseType,
    Platform,
    interactive_bot_handler
)
from .intelligence.response_types import (
    InteractiveResponseBuilder,
    Button,
    FormField,
    CarouselItem,
    create_search_results,
    create_booking_confirmation,
    create_pnr_status,
    create_train_tracking
)
from .telegram.handler import (
    TelegramInteractiveHandler,
    TelegramUpdate,
    telegram_interactive_handler
)
# from api.communication.bot_api import router as interactive_bot_router  # Removed to avoid circularity

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
    # 'interactive_bot_router' # Removed
]
