"""
Polling Manager
===============
Handles long polling for development and testing.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .bot import telegram_bot
from .dispatcher import TelegramDispatcher
from .config import bot_config

logger = logging.getLogger(__name__)


class PollingManager:
    """
    Manages long polling for receiving updates.
    Used for development and testing.
    """
    
    def __init__(self):
        self.dispatcher = TelegramDispatcher()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._offset = 0
        self._poll_interval = 1.0  # seconds
        self._timeout = 30  # seconds
    
    async def start(self) -> None:
        """Start polling for updates."""
        if self._running:
            logger.warning("Polling is already running")
            return
        
        self._running = True
        logger.info("Starting polling manager")
        
        # Verify bot connection
        bot_info = await self.dispatcher.get_me()
        if bot_info:
            logger.info(f"Bot connected: @{bot_info.get('result', {}).get('username', 'unknown')}")
        else:
            logger.error("Failed to connect to Telegram")
            return
        
        # Start polling loop
        self._task = asyncio.create_task(self._polling_loop())
    
    async def stop(self) -> None:
        """Stop polling."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        await self.dispatcher.close()
        logger.info("Polling manager stopped")
    
    async def _polling_loop(self) -> None:
        """Main polling loop."""
        logger.info("Polling loop started")
        
        while self._running:
            try:
                # Get updates
                updates = await self._get_updates()
                
                if updates:
                    # Process each update
                    for update in updates:
                        await telegram_bot.process_update(update)
                    
                    # Update offset
                    if updates:
                        last_update_id = updates[-1].get("update_id", 0)
                        self._offset = last_update_id + 1
                
                # Wait before next poll
                await asyncio.sleep(self._poll_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(5)  # Wait longer on error
        
        logger.info("Polling loop stopped")
    
    async def _get_updates(self) -> list:
        """Get updates from Telegram."""
        try:
            url = f"{self.dispatcher.base_url}/getUpdates"
            
            payload = {
                "offset": self._offset,
                "timeout": self._timeout,
                "allowed_updates": ["message", "callback_query"]
            }
            
            async with self.dispatcher._client as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
            
            if data.get("ok"):
                return data.get("result", [])
            else:
                logger.error(f"Error getting updates: {data}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []
    
    def is_running(self) -> bool:
        """Check if polling is running."""
        return self._running
    
    def get_status(self) -> Dict[str, Any]:
        """Get polling status."""
        return {
            "running": self._running,
            "offset": self._offset,
            "poll_interval": self._poll_interval,
            "timeout": self._timeout
        }


# Global polling manager
polling_manager = PollingManager()