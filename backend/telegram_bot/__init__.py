"""
Telegram Bot System - Production-Grade Integration
===================================================
Provides complete website functionality through Telegram with:
- Advanced command handling
- Natural language processing
- Multi-step workflows
- Context-aware conversations
- Full resilience patterns
"""

from telegram_bot.bot import TelegramBot
from telegram_bot.dispatcher import TelegramDispatcher as TelegramBotDispatcher
from telegram_bot.webhook import webhook_router as TelegramWebhookHandler

__all__ = [
    "TelegramBot",
    "TelegramBotDispatcher", 
    "TelegramWebhookHandler"
]