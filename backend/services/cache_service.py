import redis
from redis.lock import Lock
import json
import logging
from typing import Optional, Any, Dict

from backend.config import Config

logger = logging.getLogger(__name__)

class _DummyLock:
    """A dummy lock that does nothing, for use when Redis is not available."""
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def acquire(self, blocking=True, blocking_timeout=-1):
        return True

    def release(self):
        pass

class CacheService:
    """A Redis-based caching service with an in-process fallback for tests/dev when Redis is not available."""

    def __init__(self, redis_url: str = Config.REDIS_URL):
        self._in_memory: Dict[str, Any] = {}
        self.version_prefix = Config.REDIS_VERSION_PREFIX
        try:
            # Note: decode_responses=True is important for locks and general use
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
            logger.info("Successfully connected to Redis.")
        except Exception as e:
            logger.warning(f"Could not connect to Redis (falling back to in-memory cache): {e}")
            self.redis = None

    def _get_versioned_key(self, key: str) -> str:
        """Prepends the version prefix to the key."""
        return f"{self.version_prefix}:{key}"

    def is_available(self) -> bool:
        """Check if the Redis connection is available."""
        return self.redis is not None

    def get_lock(self, name: str, timeout: int = 10, blocking_timeout: int = 0) -> Lock:
        """
        Get a Redis distributed lock.

        :param name: The name of the lock.
        :param timeout: The lock's TTL in seconds.
        :param blocking_timeout: Max seconds to wait to acquire lock. 0 for non-blocking.
        :return: A lock object (either Redis-backed or a dummy).
        """
        if self.is_available():
            # Locks are not versioned as they are not for caching
            return self.redis.lock(name, timeout=timeout, blocking_timeout=blocking_timeout)
        
        logger.warning(f"Returning dummy lock for '{name}' as Redis is not available.")
        return _DummyLock(self.redis, name)

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache. Deserializes JSON."""
        versioned_key = self._get_versioned_key(key)
        if self.is_available():
            try:
                value = self.redis.get(versioned_key)
                if value:
                    logger.debug(f"CACHE HIT for key: {versioned_key}")
                    return json.loads(value)
                else:
                    logger.debug(f"CACHE MISS for key: {versioned_key}")
                    return None
            except (redis.exceptions.RedisError, json.JSONDecodeError) as e:
                logger.error(f"Failed to get value from cache for key {versioned_key}: {e}")
                return None

        # Fallback to in-memory cache
        val = self._in_memory.get(versioned_key)
        if val is not None:
            logger.debug(f"IN-MEM CACHE HIT for key: {versioned_key}")
        else:
            logger.debug(f"IN-MEM CACHE MISS for key: {versioned_key}")
        return val

    def set(self, key: str, value: Any, ttl_seconds: int = Config.CACHE_TTL_SECONDS):
        """Set a value in the cache. Serializes value to JSON when using Redis."""
        versioned_key = self._get_versioned_key(key)
        if self.is_available():
            try:
                serialized_value = json.dumps(value)
                self.redis.set(versioned_key, serialized_value, ex=ttl_seconds)
                logger.debug(f"CACHE SET for key: {versioned_key} with TTL: {ttl_seconds}s")
            except (redis.exceptions.RedisError, TypeError) as e:
                logger.error(f"Failed to set value in cache for key {versioned_key}: {e}")
            return

        # Fallback to in-memory cache (no TTL support for simple fallback)
        self._in_memory[versioned_key] = value
        logger.debug(f"IN-MEM CACHE SET for key: {versioned_key}")

    def delete(self, key: str):
        """Delete a key from the cache."""
        versioned_key = self._get_versioned_key(key)
        if self.is_available():
            try:
                self.redis.delete(versioned_key)
                logger.debug(f"CACHE DELETE for key: {versioned_key}")
            except redis.exceptions.RedisError as e:
                logger.error(f"Failed to delete key {versioned_key} from cache: {e}")
            return

        self._in_memory.pop(versioned_key, None)
        logger.debug(f"IN-MEM CACHE DELETE for key: {versioned_key}")

# Global instance to be used across the application
cache_service = CacheService()