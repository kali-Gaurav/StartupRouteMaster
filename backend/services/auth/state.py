import json
import logging
from typing import Any, Dict, Optional

from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger(__name__)

class UserStateManager:
    """
    Manages conversational state for each Telegram user using Redis.
    This enables multi-step workflows and contextual interactions.
    """
    
    def __init__(self, prefix: str = "telegram_user_state:"):
        self.prefix = prefix
        self.redis_client = multi_layer_cache.redis # Assuming multi_layer_cache provides a direct redis client

    def _get_key(self, chat_id: int) -> str:
        """Generates the Redis key for a given chat ID."""
        return f"{self.prefix}{chat_id}"

    async def get_state(self, chat_id: int) -> Dict[str, Any]:
        """Retrieves the current state for a user."""
        try:
            state_json = await self.redis_client.get(self._get_key(chat_id))
            if state_json:
                return json.loads(state_json)
        except Exception as e:
            logger.error(f"Error retrieving state for chat_id {chat_id}: {e}")
        return {}

    async def set_state(self, chat_id: int, state: Dict[str, Any], ttl: int = 3600):
        """
        Sets or updates the state for a user.
        State is stored as a JSON string with an optional TTL (default: 1 hour).
        """
        try:
            state_json = json.dumps(state)
            await self.redis_client.set(self._get_key(chat_id), state_json, ex=ttl)
        except Exception as e:
            logger.error(f"Error setting state for chat_id {chat_id}: {e}")

    async def update_state(self, chat_id: int, updates: Dict[str, Any], ttl: int = 3600):
        """
        Updates specific fields within the current state, merging new values.
        If a key in 'updates' has a value of None, that key is removed from the state.
        """
        current_state = await self.get_state(chat_id)
        for key, value in updates.items():
            if value is None:
                if key in current_state:
                    del current_state[key]
            else:
                current_state[key] = value
        await self.set_state(chat_id, current_state, ttl)

    async def clear_state(self, chat_id: int):
        """Clears the entire state for a user."""
        try:
            await self.redis_client.delete(self._get_key(chat_id))
        except Exception as e:
            logger.error(f"Error clearing state for chat_id {chat_id}: {e}")

user_state_manager = UserStateManager()
