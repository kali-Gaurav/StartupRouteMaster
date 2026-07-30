from services.cache_service import cache_service
import hashlib
import logging
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ChatCache:
    """
    Caches AI responses for frequent, non-personalized questions.
    """
    
    TTL = 86400 # 24 hours
    KEY_PREFIX = "chat:cache:"

    @staticmethod
    def _get_hash(text: str) -> str:
        # Normalize and hash
        normalized = " ".join(text.lower().split())
        return hashlib.blake2b(normalized.encode()).hexdigest()

    @staticmethod
    def get(message: str) -> Optional[Dict[str, Any]]:
        if not cache_service or not cache_service.is_available():
            return None
            
        key = f"{ChatCache.KEY_PREFIX}{ChatCache._get_hash(message)}"
        try:
            cached = cache_service.redis.get(key)
            if cached:
                logger.info("Chat Cache HIT")
                return json.loads(cached)
        except Exception:
            pass
        return None

    @staticmethod
    def set(message: str, response_data: Dict[str, Any]):
        if not cache_service or not cache_service.is_available():
            return
            
        # Only cache general answers (not specific to a PNR or user)
        if len(message) < 10 or "pnr" in message.lower() or "my" in message.lower():
            return

        key = f"{ChatCache.KEY_PREFIX}{ChatCache._get_hash(message)}"
        try:
            cache_service.redis.set(key, json.dumps(response_data), ex=ChatCache.TTL)
        except Exception as e:
            logger.error(f"Failed to set chat cache: {e}")
