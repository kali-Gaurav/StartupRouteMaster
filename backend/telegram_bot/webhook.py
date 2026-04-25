"""
Webhook Handler
===============
Handles Telegram webhooks for production deployment.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from .bot import telegram_bot
from .config import bot_config

logger = logging.getLogger(__name__)

webhook_router = APIRouter()


@webhook_router.post(bot_config.webhook_path)
async def telegram_webhook(request: Request) -> Dict[str, str]:
    """
    Telegram webhook endpoint.
    
    This endpoint receives all updates from Telegram when configured
    in webhook mode.
    """
    try:
        # Get update from request
        update = await request.json()
        
        # Log update (for debugging)
        logger.debug(f"Received webhook update: {update.get('update_id', 'unknown')}")
        
        # Process update
        response = await telegram_bot.process_update(update)
        
        if response:
            logger.debug(f"Webhook response sent for update {update.get('update_id')}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@webhook_router.get("/webhooks/telegram/health")
async def webhook_health() -> Dict[str, str]:
    """Webhook health check."""
    return {"status": "healthy"}


@webhook_router.get("/webhooks/telegram/info")
async def webhook_info() -> Dict[str, Any]:
    """Get webhook information."""
    health = telegram_bot.get_health()
    return {
        "bot_status": health["status"],
        "webhook_path": bot_config.webhook_path,
        "health": health
    }