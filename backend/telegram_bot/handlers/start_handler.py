"""
Start Handler
=============
Handles /start and welcome messages.
"""

import logging
from datetime import datetime
from typing import Optional

from ..schemas import (
    TelegramMessage, UserContext, BotResponse, 
    IntentType, HandlerResult, HandlerResultStatus
)
from ..dispatcher import telegram_dispatcher
from ..keyboards import keyboard_builder
from ..user_session_manager import user_session_manager

logger = logging.getLogger(__name__)


class StartHandler:
    """Handles start command and welcome messages."""
    
    WELCOME_MESSAGE = """
🚀 <b>Welcome to Rail Assistant!</b>

Your AI-powered travel companion for seamless train bookings and real-time updates.

━━━━━━━━━━━━━━━━━━━━━━━━
<b>What I can do:</b>

🎫 <b>Book Tickets</b>
   Search & book train tickets instantly

🔍 <b>Search Trains</b>
   Find routes, check availability & compare

📜 <b>PNR Status</b>
   Track your bookings in real-time

💳 <b>My Wallet</b>
   Manage payments & transactions

🚨 <b>SOS Emergency</b>
   One-tap emergency assistance

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Quick Start:</b>
• Type /help for all commands
• Tap 🔍 Search Trains to begin
• Your bookings are synced with the website

<i>Happy travels! 🚂</i>
"""
    
    RETURNING_MESSAGE = """
👋 <b>Welcome back!</b>

Great to see you again. How can I help you today?

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Quick Actions:</b>
• 🎫 View my bookings
• 🔍 Search for trains
• 📜 Check PNR status
• 💳 Wallet & payments

<i>Type or tap below to continue!</i>
"""
    
    async def handle(
        self,
        message: TelegramMessage,
        context: UserContext,
        intent_result
    ) -> HandlerResult:
        """
        Handle /start command.
        
        Args:
            message: Incoming message
            context: User context
            intent_result: Intent classification result
            
        Returns:
            HandlerResult with response
        """
        chat_id = message.chat.id
        user_id = message.from_user.id
        first_name = message.from_user.first_name or "Traveler"
        
        try:
            # Check if returning user
            is_returning = context.message_count > 0
            
            # Update session
            await user_session_manager.update_context(
                chat_id,
                {
                    "state": "idle",
                    "intent": None,
                    "data": {}
                }
            )
            
            # Select message based on user history
            if is_returning:
                text = self.RETURNING_MESSAGE.replace("{name}", first_name)
            else:
                text = self.WELCOME_MESSAGE
            
            # Create response
            response = BotResponse(
                chat_id=chat_id,
                text=text,
                keyboard=keyboard_builder.main_menu()
            )
            
            # Log welcome
            logger.info(f"Welcome message sent to user {user_id} (returning: {is_returning})")
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=response,
                next_state="idle"
            )
            
        except Exception as e:
            logger.error(f"Error in start handler: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"❌ Error: {str(e)}"
                ),
                error=str(e)
            )


# Global instance
start_handler = StartHandler()