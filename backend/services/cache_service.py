import redis
import json
import logging
from typing import Optional, Any

from config import Config

logger = logging.getLogger(__name__)

class CacheService:
    """A Redis-based caching service."""

    def __init__(self, redis_url: str = Config.REDIS_URL):
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
            logger.info("Successfully connected to Redis.")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Could not connect to Redis: {e}")
            self.redis = None

    def is_available(self) -> bool:
        """Check if the Redis connection is available."""
        return self.redis is not None

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache. Deserializes JSON."""
        if not self.is_available():
            return None
        
        try:
            value = self.redis.get(key)
            if value:
                logger.debug(f"CACHE HIT for key: {key}")
                return json.loads(value)
            else:
                logger.debug(f"CACHE MISS for key: {key}")
                return None
        except (redis.exceptions.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get value from cache for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = Config.CACHE_TTL_SECONDS):
        """Set a value in the cache. Serializes value to JSON."""
        if not self.is_available():
            return
        
        try:
            serialized_value = json.dumps(value)
            self.redis.set(key, serialized_value, ex=ttl_seconds)
            logger.debug(f"CACHE SET for key: {key} with TTL: {ttl_seconds}s")
        except (redis.exceptions.RedisError, TypeError) as e:
            logger.error(f"Failed to set value in cache for key {key}: {e}")

    def delete(self, key: str):
        """Delete a key from the cache."""
        if not self.is_available():
            return
        
        try:
            self.redis.delete(key)
            logger.debug(f"CACHE DELETE for key: {key}")
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to delete key {key} from cache: {e}")

# Global instance to be used across the application
cache_service = CacheService()