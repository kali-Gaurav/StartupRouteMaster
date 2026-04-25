"""
Telegram Bot Entry Point
========================
Run the bot in polling or webhook mode.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram_bot.bot import telegram_bot
from telegram_bot.polling import polling_manager
from telegram_bot.config import bot_config, BotMode

# Configure logging
logging.basicConfig(
    level=getattr(logging, bot_config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def run_polling():
    """Run bot in polling mode."""
    logger.info("Starting bot in polling mode...")
    await telegram_bot.start()
    await polling_manager.start()
    
    # Keep running
    try:
        while polling_manager.is_running():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await stop_bot()


async def run_webhook():
    """Run bot in webhook mode."""
    logger.info("Starting bot in webhook mode...")
    await telegram_bot.start()
    
    # Webhook is handled by FastAPI
    # This function just starts the bot
    logger.info(f"Webhook endpoint: {bot_config.webhook_path}")
    
    # Keep running
    try:
        while telegram_bot.is_running():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await stop_bot()


async def stop_bot():
    """Stop the bot."""
    logger.info("Stopping bot...")
    await polling_manager.stop()
    await telegram_bot.stop()
    logger.info("Bot stopped")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram Bot")
    parser.add_argument(
        "--mode",
        choices=["polling", "webhook"],
        default=bot_config.bot_mode.value,
        help="Bot operation mode"
    )
    parser.add_argument(
        "--setup-webhook",
        action="store_true",
        help="Setup webhook and exit"
    )
    
    args = parser.parse_args()
    
    # Setup webhook if requested
    if args.setup_webhook:
        from telegram_bot.dispatcher import telegram_dispatcher
        import httpx
        
        async def setup_webhook():
            if not bot_config.webhook_url:
                logger.error("WEBHOOK_URL not configured")
                return
            
            url = f"{bot_config.webhook_url}{bot_config.webhook_path}"
            token = bot_config.bot_token
            
            async with httpx.AsyncClient() as client:
                # Set webhook
                res = await client.post(
                    f"https://api.telegram.org/bot{token}/setWebhook",
                    json={"url": url}
                )
                result = res.json()
                
                if result.get("ok"):
                    logger.info(f"Webhook set to: {url}")
                else:
                    logger.error(f"Failed to set webhook: {result}")
        
        asyncio.run(setup_webhook())
        return
    
    # Run bot
    if args.mode == "polling":
        asyncio.run(run_polling())
    else:
        asyncio.run(run_webhook())


if __name__ == "__main__":
    main()