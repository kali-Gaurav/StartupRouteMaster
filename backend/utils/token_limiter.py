from services.cache_service import cache_service
import time
import logging

logger = logging.getLogger(__name__)

class TokenLimiter:
    """
    Tracks and limits AI token usage per session using Redis.
    Default limit: 10,000 tokens per 24 hours.
    """
    
    DAILY_LIMIT = 10000
    KEY_PREFIX = "chat:usage:"

    @staticmethod
    def check_limit(session_id: str) -> bool:
        """
        Returns True if session is within limits, False otherwise.
        """
        if not cache_service or not cache_service.is_available():
            return True # Fallback: Allow if Redis is down
            
        key = f"{TokenLimiter.KEY_PREFIX}{session_id}"
        usage = cache_service.redis.get(key)
        
        if usage and int(usage) >= TokenLimiter.DAILY_LIMIT:
            return False
            
        return True

    @staticmethod
    def update_usage(session_id: str, tokens: int):
        """
        Increments the token usage for the given session.
        """
        if not cache_service or not cache_service.is_available():
            return
            
        key = f"{TokenLimiter.KEY_PREFIX}{session_id}"
        
        # Increment usage and set 24h expiry if new
        try:
            current = cache_service.redis.incrby(key, tokens)
            if current == tokens:
                cache_service.redis.expire(key, 86400) # 24 hours
        except Exception as e:
            logger.error(f"Failed to update token usage: {e}")
