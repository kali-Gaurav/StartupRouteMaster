"""
Telegram Bot FastAPI Integration
=================================

Integrates the Telegram bot webhook with the main FastAPI application.

Author: RouteMaster Team
Version: 1.0.0
"""

import logging
import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any

from .config import bot_config

logger = logging.getLogger(__name__)

# Create router for Telegram webhook
telegram_router = APIRouter(prefix="/telegram", tags=["Telegram"])


@telegram_router.post("/webhook")
async def telegram_webhook(request: Request) -> Dict[str, str]:
    """
    Telegram webhook endpoint.
    
    This endpoint receives all updates from Telegram when configured
    in webhook mode.
    """
    from .bot import telegram_bot
    try:
        # Verify secret token if configured
        webhook_secret = bot_config.webhook_url # This is a bit weird in config, let's use a direct env fetch or update config
        # Actually let's use os.getenv directly to be safe or update TelegramBotConfig
        secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        expected_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
        
        if expected_secret and secret_header != expected_secret:
            logger.warning(f"Unauthorized webhook attempt from {request.client.host if request.client else 'unknown'}")
            raise HTTPException(status_code=403, detail="Forbidden")

        # Get update from request
        update = await request.json()
        
        # Log update (for debugging)
        update_id = update.get("update_id", "unknown")
        logger.info(f"Received Telegram webhook update: {update_id}")
        
        # Process update through the bot
        response = await telegram_bot.process_update(update)
        
        if response:
            logger.debug(f"Webhook response sent for update {update_id}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@telegram_router.get("/webhook/health")
async def webhook_health() -> Dict[str, str]:
    """Webhook health check."""
    return {"status": "healthy", "bot": "running"}


@telegram_router.get("/webhook/info")
async def webhook_info() -> Dict[str, Any]:
    """Get webhook and bot information."""
    from .bot import telegram_bot
    health = telegram_bot.get_health()
    return {
        "status": "healthy",
        "webhook_path": "/telegram/webhook",
        "bot_status": health["status"],
        "health": health
    }


@telegram_router.post("/webhook/test")
async def test_webhook() -> Dict[str, str]:
    """
    Test endpoint to verify webhook is working.
    Sends a test message to the configured chat ID.
    """
    try:
        from .dispatcher import telegram_dispatcher
        
        test_chat_id = bot_config.test_chat_id
        if not test_chat_id:
            return {"status": "error", "message": "TEST_CHAT_ID not configured"}
        
        # Send test message
        success = await telegram_dispatcher.send_message(
            chat_id=test_chat_id,
            text="✅ <b>Telegram Bot Webhook Test</b>\n\nYour bot is connected and working correctly!",
            parse_mode="HTML"
        )
        
        if success:
            return {"status": "success", "message": "Test message sent"}
        else:
            return {"status": "error", "message": "Failed to send test message"}
            
    except Exception as e:
        logger.error(f"Test webhook error: {e}")
        return {"status": "error", "message": str(e)}


def setup_telegram_webhook(webhook_url: str) -> bool:
    """
    Set up the Telegram webhook.
    
    Args:
        webhook_url: Full URL for the webhook endpoint
        
    Returns:
        True if successful
    """
    import httpx
    import asyncio
    
    async def _setup():
        token = bot_config.bot_token
        url = f"{webhook_url}/telegram/webhook"
        
        async with httpx.AsyncClient() as client:
            # Set webhook
            res = await client.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={"url": url}
            )
            result = res.json()
            
            if result.get("ok"):
                logger.info(f"Telegram webhook set to: {url}")
                return True
            else:
                logger.error(f"Failed to set webhook: {result}")
                return False
    
    try:
        return asyncio.get_event_loop().run_until_complete(_setup())
    except Exception as e:
        logger.error(f"Error setting up webhook: {e}")
        return False


def register_flows():
    """Register all conversational flows."""
    from .flow_handler import flow_handler, Flow, FlowStep
    from .schemas import UserState
    
    # Profile Update Flow
    profile_flow = Flow(
        name="Profile Update",
        state=UserState.PROFILE,
        steps=[
            FlowStep(
                id="name",
                prompt="👤 Please enter your <b>Full Name</b>:",
                validator=lambda t: len(t) > 2
            ),
            FlowStep(
                id="email",
                prompt="📧 Now, please enter your <b>Email Address</b>:",
                validator=lambda t: "@" in t and "." in t
            )
        ]
    )
    flow_handler.register_flow(profile_flow)
    logger.info("Conversational flows registered")


def register_with_app(app) -> None:
    """
    Register Telegram routes with FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    app.include_router(telegram_router)
    
    # Register flows
    register_flows()
    
    logger.info("Telegram webhook routes and flows registered with FastAPI app")


# Export
__all__ = [
    'telegram_router',
    'setup_telegram_webhook',
    'register_with_app'
]
