import os
import logging
from telegram import Bot
from telegram.constants import ParseMode
import asyncio

logger = logging.getLogger(__name__)

async def send_ticket_to_telegram(telegram_id: str, file_path: str, caption: str):
    """
    Task 41: Telegram Ticket Dispatcher.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not found. Skipping dispatch.")
        return False
        
    try:
        bot = Bot(token=token)
        async with bot:
            await bot.send_document(
                chat_id=telegram_id,
                document=open(file_path, 'rb'),
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        logger.info(f"Ticket sent to Telegram ID: {telegram_id}")
        return True
    except Exception as e:
        logger.error(f"Telegram dispatch failed: {e}")
        return False
