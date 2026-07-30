"""
Telegram Interactive Handler
=============================

Telegram-specific bot handler with inline keyboards and callback queries.
Integrates with the main InteractiveBotHandler.

Author: RouteMaster Team
Version: 1.0.0
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
import httpx
import json

from services.intelligence.bot_handler import InteractiveBotHandler, Platform, InteractiveResponse
from services.intelligence.response_types import ResponseType, Button
from .bot import TelegramDispatcher
from services.intelligence.conversation import ConversationManager, ConversationContext, Intent

logger = logging.getLogger("telegram.interactive")


@dataclass
class TelegramUpdate:
    """Telegram update wrapper"""
    update_id: str
    message_id: Optional[str]
    chat_id: str
    user_id: str
    text: Optional[str]
    callback_query: Optional[Dict[str, Any]]
    timestamp: datetime
    
    @classmethod
    def from_update(cls, update: Dict[str, Any]) -> "TelegramUpdate":
        """Create from Telegram API update"""
        update_id = str(update.get("update_id", ""))
        
        message = update.get("message", {})
        callback = update.get("callback_query", {})
        
        if callback:
            message = callback.get("message", {})
            data = callback.get("data", "")
            user = callback.get("from", {})
            chat = message.get("chat", {})
            
            return cls(
                update_id=update_id,
                message_id=str(message.get("message_id", "")),
                chat_id=str(chat.get("id", "")),
                user_id=str(user.get("id", "")),
                text=data,  # Callback data in text field
                callback_query=callback,
                timestamp=datetime.utcnow()
            )
        
        user = message.get("from", {})
        chat = message.get("chat", {})
        
        return cls(
            update_id=update_id,
            message_id=str(message.get("message_id", "")),
            chat_id=str(chat.get("id", "")),
            user_id=str(user.get("id", "")),
            text=message.get("text", ""),
            callback_query=None,
            timestamp=datetime.utcnow()
        )


class TelegramInteractiveHandler:
    """
    Telegram-specific handler for interactive bot conversations.
    Handles messages, callback queries, and inline keyboards.
    """
    
    def __init__(self):
        self.bot_handler = InteractiveBotHandler()
        self.telegram = TelegramDispatcher()
        self._webhook_secret: Optional[str] = None
        self._last_update_id: int = 0
        
        logger.info("TelegramInteractiveHandler initialized")
    
    def set_webhook_secret(self, secret: str):
        """Set webhook verification secret"""
        self._webhook_secret = secret
    
    async def handle_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming Telegram update.
        
        Args:
            update: Telegram update object
            
        Returns:
            Response dict
        """
        try:
            tg_update = TelegramUpdate.from_update(update)
            
            # Skip old updates
            update_id = int(tg_update.update_id) if tg_update.update_id.isdigit() else 0
            if update_id <= self._last_update_id:
                return {"status": "skipped"}
            self._last_update_id = update_id
            
            # Handle callback query
            if tg_update.callback_query:
                return await self._handle_callback(tg_update)
            
            # Handle regular message
            if tg_update.text:
                return await self._handle_message(tg_update)
            
            return {"status": "ignored", "reason": "no_text"}
            
        except Exception as e:
            logger.error(f"Error handling update: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_message(self, tg_update: TelegramUpdate) -> Dict[str, Any]:
        """Handle regular message"""
        user_id = tg_update.user_id
        chat_id = tg_update.chat_id
        text = tg_update.text
        
        # Process message through bot handler
        response = await self.bot_handler.process_message(
            user_id=user_id,
            message=text,
            platform=Platform.TELEGRAM,
            chat_id=chat_id,
            metadata={
                "message_id": tg_update.message_id,
                "update_id": tg_update.update_id
            }
        )
        
        # Send response
        await self._send_response(chat_id, response)
        
        return {"status": "processed", "response_id": response.response_id}
    
    async def _handle_callback(self, tg_update: TelegramUpdate) -> Dict[str, Any]:
        """Handle callback query (button click)"""
        user_id = tg_update.user_id
        chat_id = tg_update.chat_id
        callback_data = tg_update.text or ""
        
        # Parse callback data (format: action|value)
        parts = callback_data.split("|", 1)
        action = parts[0] if parts else ""
        value = parts[1] if len(parts) > 1 else None
        
        # Get conversation
        conv = self.bot_handler.conversation_manager.get_user_conversation(user_id)
        
        # Process callback
        response = await self.bot_handler.process_callback(
            user_id=user_id,
            action=action,
            value=value,
            conversation_id=conv.conversation_id if conv else None,
            platform=Platform.TELEGRAM,
            chat_id=chat_id
        )
        
        # Answer callback query (remove loading state)
        await self._answer_callback(tg_update.callback_query.get("id", ""))
        
        # Update or send new message
        if tg_update.message_id:
            await self._edit_message(chat_id, tg_update.message_id, response)
        else:
            await self._send_response(chat_id, response)
        
        return {"status": "processed", "response_id": response.response_id}
    
    async def _send_response(self, chat_id: str, response: InteractiveResponse):
        """Send response to Telegram chat"""
        try:
            # Format message
            text = self._format_message(response)
            
            # Get keyboard
            keyboard = self._get_keyboard(response)
            
            # Send based on response type
            if response.response_type == ResponseType.CAROUSEL:
                # Send carousel as multiple messages
                for i, item in enumerate(response.carousel_items):
                    item_text = self._format_carousel_item(item)
                    item_keyboard = self._get_item_keyboard(item)
                    
                    if i == 0:
                        # First item with main content
                        await self.telegram.send_message(
                            chat_id=chat_id,
                            text=text,
                            reply_markup=keyboard
                        )
                    
                    await self.telegram.send_message(
                        chat_id=chat_id,
                        text=item_text,
                        reply_markup=item_keyboard
                    )
            
            elif response.response_type == ResponseType.SOS:
                # SOS with danger buttons
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
                
                # Also send as location request for emergency
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text="📍 Please share your current location for faster assistance:",
                    reply_markup={
                        "keyboard": [
                            [{"text": "📍 Share Location", "request_location": True}]
                        ],
                        "resize_keyboard": True
                    }
                )
            
            elif response.response_type == ResponseType.FORM:
                # Send form as text with instructions
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
            
            elif response.response_type == ResponseType.REDIRECT:
                # Send with link button
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
            
            elif response.response_type == ResponseType.FEEDBACK:
                # Rating buttons
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
            
            elif response.response_type == ResponseType.CONFIRMATION:
                # Confirm/Cancel buttons
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
            
            else:
                # Default: text with buttons
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard
                )
                
        except Exception as e:
            logger.error(f"Error sending response: {e}")
    
    def _format_message(self, response: InteractiveResponse) -> str:
        """Format response message for Telegram"""
        parts = []
        
        if response.title:
            parts.append(f"<b>{response.title}</b>")
        
        if response.subtitle:
            parts.append(f"<i>{response.subtitle}</i>")
        
        if response.content:
            parts.append(response.content)
        
        return "\n\n".join(parts) if parts else response.content or ""
    
    def _format_carousel_item(self, item) -> str:
        """Format carousel item for Telegram"""
        parts = []
        
        if item.title:
            parts.append(f"<b>{item.title}</b>")
        
        if item.subtitle:
            parts.append(f"<i>{item.subtitle}</i>")
        
        if item.description:
            parts.append(item.description)
        
        return "\n\n".join(parts) if parts else item.title or ""
    
    def _get_keyboard(self, response: InteractiveResponse) -> Optional[Dict[str, Any]]:
        """Convert buttons to Telegram inline keyboard"""
        if not response.buttons:
            return None
        
        # Group buttons in rows of 2
        keyboard = []
        row = []
        
        for button in response.buttons:
            row.append({
                "text": button.text,
                "callback_data": f"{button.action}|{button.value or ''}"
            })
            
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        return {"inline_keyboard": keyboard} if keyboard else None
    
    def _get_item_keyboard(self, item) -> Optional[Dict[str, Any]]:
        """Get keyboard for carousel item"""
        if not item.buttons:
            return None
        
        keyboard = []
        row = []
        
        for button in item.buttons:
            row.append({
                "text": button.text,
                "callback_data": f"{button.action}|{button.value or ''}"
            })
            
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        return {"inline_keyboard": keyboard} if keyboard else None
    
    async def _answer_callback(self, callback_id: str):
        """Answer callback query (remove loading state)"""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.telegram.base_url}/answerCallbackQuery",
                    json={"callback_query_id": callback_id}
                )
        except Exception as e:
            logger.error(f"Error answering callback: {e}")
    
    async def _edit_message(
        self,
        chat_id: str,
        message_id: str,
        response: InteractiveResponse
    ):
        """Edit existing message"""
        try:
            text = self._format_message(response)
            keyboard = self._get_keyboard(response)
            
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.telegram.base_url}/editMessageText",
                    json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": keyboard
                    }
                )
        except Exception as e:
            logger.error(f"Error editing message: {e}")
    
    async def set_webhook(self, webhook_url: str) -> bool:
        """Set Telegram webhook"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.telegram.base_url}/setWebhook",
                    json={
                        "url": webhook_url,
                        "secret_token": self._webhook_secret
                    }
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Error setting webhook: {e}")
            return False
    
    async def get_webhook_info(self) -> Dict[str, Any]:
        """Get webhook info"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.telegram.base_url}/getWebhookInfo"
                )
                return response.json()
        except Exception as e:
            logger.error(f"Error getting webhook info: {e}")
            return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics"""
        return {
            "bot_handler": self.bot_handler.get_stats(),
            "telegram": {
                "last_update_id": self._last_update_id
            }
        }


# Global instance
telegram_interactive_handler = TelegramInteractiveHandler()

# Export
__all__ = [
    'TelegramUpdate',
    'TelegramInteractiveHandler',
    'telegram_interactive_handler'
]
