import httpx
import logging
from typing import Optional, List, Union
from database.config import Config

logger = logging.getLogger(__name__)

class TelegramService:
    """
    Handles emergency broadcasts and notifications via Telegram Bot API.
    """
    
    def __init__(self):
        self.bot_token = Config.TELEGRAM_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, chat_id: Union[str, int], text: str):
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured. Skipping message.")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "Markdown"
                    },
                    timeout=10.0
                )
                res.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def broadcast_sos(self, user_name: str, lat: float, lng: float, telegram_ids: List[Union[str, int]]):
        """
        Sends an SOS alert to a list of Telegram IDs.
        """
        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        message = (
            f"🚨 *EMERGENCY SOS ALERT* 🚨\n\n"
            f"Passenger: *{user_name}*\n"
            f"Location: [{lat}, {lng}]({maps_url})\n\n"
            f"⚠️ Help is requested immediately. Click the link above to see the live location."
        )
        
        results = []
        for tid in telegram_ids:
            success = await self.send_message(tid, message)
            results.append(success)
        
        return all(results)

from typing import Union
telegram_service = TelegramService()
