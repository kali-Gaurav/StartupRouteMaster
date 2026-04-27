"""
Interactive Bot API Endpoints
=============================

FastAPI endpoints for the interactive chatbot system.
Provides message processing, callback handling, and conversation management.

Author: RouteMaster Team
Version: 1.0.0
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.interactive_bot_handler import (
    InteractiveBotHandler, Platform, InteractiveResponse
)
from services.telegram_interactive_handler import TelegramInteractiveHandler
from services.conversation_manager import ConversationManager, ConversationContext

logger = logging.getLogger("api.interactive")

# Create router
router = APIRouter(prefix="/api/bot", tags=["interactive_bot"])

# Global instances
bot_handler = InteractiveBotHandler()
telegram_handler = TelegramInteractiveHandler()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class MessageRequest(BaseModel):
    """Request model for bot message"""
    user_id: str = Field(..., description="User identifier")
    message: str = Field(..., description="User message")
    platform: str = Field("telegram", description="Platform: telegram, web, whatsapp")
    chat_id: Optional[str] = Field(None, description="Platform-specific chat ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class CallbackRequest(BaseModel):
    """Request model for callback query"""
    user_id: str = Field(..., description="User identifier")
    action: str = Field(..., description="Callback action")
    value: Optional[str] = Field(None, description="Callback value")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    platform: str = Field("telegram", description="Platform")
    chat_id: Optional[str] = Field(None, description="Chat ID")


class InteractiveResponseModel(BaseModel):
    """Response model for interactive responses"""
    response_id: str
    response_type: str
    content: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    buttons: List[Dict[str, Any]] = []
    carousel_items: List[Dict[str, Any]] = []
    form_fields: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    timestamp: str


class TelegramWebhookRequest(BaseModel):
    """Telegram webhook request"""
    update_id: int
    message: Optional[Dict[str, Any]] = None
    callback_query: Optional[Dict[str, Any]] = None


class ConversationRequest(BaseModel):
    """Request to manage conversation"""
    user_id: str
    action: str = Field(..., description="Action: get, end, clear")


# ============================================================================
# MESSAGE PROCESSING ENDPOINTS
# ============================================================================

@router.post("/message", response_model=InteractiveResponseModel)
async def process_message(request: MessageRequest):
    """
    Process a user message and return an interactive response.
    
    This endpoint handles all incoming messages and generates
    appropriate interactive responses based on user intent.
    
    Example:
    ```json
    {
        "user_id": "user123",
        "message": "Search trains from NDLS to BCT tomorrow",
        "platform": "telegram",
        "chat_id": "123456789"
    }
    ```
    """
    try:
        # Convert platform string to enum
        platform = Platform(request.platform.lower())
        
        # Process message
        response = await bot_handler.process_message(
            user_id=request.user_id,
            message=request.message,
            platform=platform,
            chat_id=request.chat_id,
            metadata=request.metadata
        )
        
        return InteractiveResponseModel(
            response_id=response.response_id,
            response_type=response.response_type.value,
            content=response.content,
            title=response.title,
            subtitle=response.subtitle,
            buttons=[{
                "text": b.text,
                "action": b.action,
                "value": b.value,
                "style": b.style
            } for b in response.buttons],
            carousel_items=[{
                "item_id": ci.item_id,
                "title": ci.title,
                "subtitle": ci.subtitle,
                "description": ci.description,
                "buttons": [{"text": b.text, "action": b.action} for b in ci.buttons]
            } for ci in response.carousel_items],
            form_fields=[{
                "field_id": ff.field_id,
                "field_type": ff.field_type,
                "label": ff.label,
                "required": ff.required,
                "options": ff.options
            } for ff in response.form_fields],
            metadata=response.metadata,
            timestamp=response.timestamp.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/callback", response_model=InteractiveResponseModel)
async def process_callback(request: CallbackRequest):
    """
    Process a callback query (button click, etc.)
    
    Handles user interactions with inline keyboards and buttons.
    """
    try:
        platform = Platform(request.platform.lower())
        
        response = await bot_handler.process_callback(
            user_id=request.user_id,
            action=request.action,
            value=request.value,
            conversation_id=request.conversation_id,
            platform=platform,
            chat_id=request.chat_id
        )
        
        return InteractiveResponseModel(
            response_id=response.response_id,
            response_type=response.response_type.value,
            content=response.content,
            title=response.title,
            subtitle=response.subtitle,
            buttons=[{
                "text": b.text,
                "action": b.action,
                "value": b.value,
                "style": b.style
            } for b in response.buttons],
            carousel_items=[{
                "item_id": ci.item_id,
                "title": ci.title,
                "subtitle": ci.subtitle,
                "description": ci.description,
                "buttons": [{"text": b.text, "action": b.action} for b in ci.buttons]
            } for ci in response.carousel_items],
            form_fields=[{
                "field_id": ff.field_id,
                "field_type": ff.field_type,
                "label": ff.label,
                "required": ff.required,
                "options": ff.options
            } for ff in response.form_fields],
            metadata=response.metadata,
            timestamp=response.timestamp.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error processing callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TELEGRAM WEBHOOK ENDPOINTS
# ============================================================================

@router.post("/telegram/webhook")
async def telegram_webhook(
    request: TelegramWebhookRequest,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
):
    """
    Telegram webhook endpoint.
    
    Receives updates from Telegram and processes them.
    """
    try:
        # Verify secret token if configured
        if telegram_handler._webhook_secret:
            if x_telegram_bot_api_secret_token != telegram_handler._webhook_secret:
                raise HTTPException(status_code=403, detail="Invalid secret token")
        
        # Convert to dict format
        update = request.dict(exclude_none=True)
        
        # Process update
        result = await telegram_handler.handle_update(update)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/telegram/webhook/set")
async def set_telegram_webhook(webhook_url: str, secret_token: Optional[str] = None):
    """
    Set Telegram webhook URL.
    
    Requires the webhook URL and optional secret token.
    """
    try:
        if secret_token:
            telegram_handler.set_webhook_secret(secret_token)
        
        success = await telegram_handler.set_webhook(webhook_url)
        
        if success:
            return {"status": "success", "webhook_url": webhook_url}
        else:
            raise HTTPException(status_code=500, detail="Failed to set webhook")
            
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telegram/webhook/info")
async def get_telegram_webhook_info():
    """Get Telegram webhook information"""
    try:
        info = await telegram_handler.get_webhook_info()
        return info
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CONVERSATION MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/conversation/{user_id}")
async def get_conversation(user_id: str):
    """
    Get conversation for a user.
    
    Returns the current conversation state and context.
    """
    try:
        conv = bot_handler.conversation_manager.get_user_conversation(user_id)
        
        if not conv:
            return {"status": "no_conversation", "user_id": user_id}
        
        return {
            "status": "active",
            "conversation_id": conv.conversation_id,
            "state": conv.state.value,
            "intent": conv.intent.value,
            "entities": conv.entities,
            "history_count": len(conv.history),
            "created_at": conv.created_at.isoformat(),
            "last_interaction": conv.last_interaction.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversation/end")
async def end_conversation(request: ConversationRequest):
    """
    End a user's conversation.
    
    Clears the conversation state and context.
    """
    try:
        bot_handler.conversation_manager.end_conversation(request.user_id)
        
        return {
            "status": "ended",
            "user_id": request.user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error ending conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/{user_id}/history")
async def get_conversation_history(
    user_id: str,
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get conversation history for a user.
    
    Returns the last N messages in the conversation.
    """
    try:
        conv = bot_handler.conversation_manager.get_user_conversation(user_id)
        
        if not conv:
            return {"status": "no_conversation", "user_id": user_id}
        
        return {
            "status": "success",
            "user_id": user_id,
            "conversation_id": conv.conversation_id,
            "history": conv.history[-limit:],
            "total_messages": len(conv.history)
        }
        
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STATS AND HEALTH ENDPOINTS
# ============================================================================

@router.get("/stats")
async def get_stats():
    """
    Get bot statistics.
    
    Returns usage stats and system health.
    """
    try:
        stats = bot_handler.get_stats()
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            **stats
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "interactive_bot",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# QUICK ACTION ENDPOINTS
# ============================================================================

@router.get("/quick/search")
async def quick_search(
    user_id: str = Query(...),
    from_station: str = Query(...),
    to_station: str = Query(...),
    date: str = Query(...),
    chat_id: Optional[str] = Query(None)
):
    """
    Quick train search endpoint.
    
    Returns interactive search results.
    """
    try:
        message = f"Search trains from {from_station} to {to_station} on {date}"
        
        response = await bot_handler.process_message(
            user_id=user_id,
            message=message,
            platform=Platform.TELEGRAM,
            chat_id=chat_id,
            metadata={
                "from_station": from_station,
                "to_station": to_station,
                "date": date
            }
        )
        
        return {
            "status": "success",
            "response_type": response.response_type.value,
            "response_id": response.response_id
        }
        
    except Exception as e:
        logger.error(f"Error in quick search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick/pnr/{pnr}")
async def quick_pnr_check(
    pnr: str,
    user_id: str = Query(...),
    chat_id: Optional[str] = Query(None)
):
    """
    Quick PNR check endpoint.
    
    Returns interactive PNR status.
    """
    try:
        message = f"Check PNR {pnr}"
        
        response = await bot_handler.process_message(
            user_id=user_id,
            message=message,
            platform=Platform.TELEGRAM,
            chat_id=chat_id,
            metadata={"pnr": pnr}
        )
        
        return {
            "status": "success",
            "response_type": response.response_type.value,
            "response_id": response.response_id
        }
        
    except Exception as e:
        logger.error(f"Error in quick PNR check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick/track/{train_number}")
async def quick_train_track(
    train_number: str,
    user_id: str = Query(...),
    chat_id: Optional[str] = Query(None)
):
    """
    Quick train tracking endpoint.
    
    Returns interactive train tracking info.
    """
    try:
        message = f"Track train {train_number}"
        
        response = await bot_handler.process_message(
            user_id=user_id,
            message=message,
            platform=Platform.TELEGRAM,
            chat_id=chat_id,
            metadata={"train_number": train_number}
        )
        
        return {
            "status": "success",
            "response_type": response.response_type.value,
            "response_id": response.response_id
        }
        
    except Exception as e:
        logger.error(f"Error in quick train track: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Export router
__all__ = ['router', 'bot_handler', 'telegram_handler']