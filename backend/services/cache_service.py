import redis
from redis.lock import Lock
import json
import logging
from typing import Optional, Any, Dict
import time # New: Import time for duration calculation
from collections import OrderedDict

from config import Config
from utils.metrics import LOCK_ACQUISITION_ATTEMPTS_TOTAL, LOCK_HOLD_DURATION_SECONDS # New: Import custom metrics

logger = logging.getLogger(__name__)

class LocalLRU:
    """Simple In-Memory LRU for Layer 0 caching."""
    def __init__(self, capacity: int = 1000):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: Any):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def delete(self, key: str):
        self.cache.pop(key, None)

class _DummyLock:
    """A dummy lock that does nothing, for use when Redis is not available."""
    def __init__(self, *args, **kwargs):
        self._acquire_time = None # New

    def __enter__(self):
        self._acquire_time = time.time() # New
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._acquire_time: # New
            LOCK_HOLD_DURATION_SECONDS.labels(lock_name="dummy_lock").observe(time.time() - self._acquire_time) # New
        pass

    def acquire(self, blocking=True, blocking_timeout=-1):
        LOCK_ACQUISITION_ATTEMPTS_TOTAL.labels(lock_name="dummy_lock", outcome="attempt").inc() # New
        self._acquire_time = time.time() # New
        LOCK_ACQUISITION_ATTEMPTS_TOTAL.labels(lock_name="dummy_lock", outcome="acquired").inc() # New
        return True

    def release(self):
        if self._acquire_time: # New
            LOCK_HOLD_DURATION_SECONDS.labels(lock_name="dummy_lock").observe(time.time() - self._acquire_time) # New
            self._acquire_time = None # Reset after release # New
        pass

class InstrumentedLock:
    """A wrapper around redis.lock.Lock to add Prometheus instrumentation."""
    def __init__(self, lock: Lock, name: str):
        self._lock = lock
        self._name = name
        self._acquire_time = None

    def acquire(self, blocking: bool = True, blocking_timeout: float = -1) -> bool:
        LOCK_ACQUISITION_ATTEMPTS_TOTAL.labels(lock_name=self._name, outcome="attempt").inc()
        acquired = self._lock.acquire(blocking=blocking, blocking_timeout=blocking_timeout)
        if acquired:
            self._acquire_time = time.time()
            LOCK_ACQUISITION_ATTEMPTS_TOTAL.labels(lock_name=self._name, outcome="acquired").inc()
        else:
            LOCK_ACQUISITION_ATTEMPTS_TOTAL.labels(lock_name=self._name, outcome="failed").inc()
        return acquired

    def release(self) -> bool:
        if self._acquire_time:
            LOCK_HOLD_DURATION_SECONDS.labels(lock_name=self._name).observe(time.time() - self._acquire_time)
            self._acquire_time = None
        released = self._lock.release()
        return released

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

class CacheService:
    """A Redis-based caching service with an in-process fallback for tests/dev when Redis is not available."""

    def __init__(self, redis_url: str = Config.REDIS_URL):
        self._in_memory: Dict[str, Any] = {}
        self._lru = LocalLRU(capacity=500) # L0 Local Cache
        self.version_prefix = Config.REDIS_VERSION_PREFIX
        try:
            # Note: decode_responses=True is important for locks and general use
            self.redis = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)
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

    def get_lock(self, name: str, timeout: int = 10, blocking_timeout: int = 0) -> InstrumentedLock: # Changed return type to InstrumentedLock
        """
        Get a Redis distributed lock.

        :param name: The name of the lock.
        :param timeout: The lock's TTL in seconds.
        :param blocking_timeout: Max seconds to wait to acquire lock. 0 for non-blocking.
        :return: An Instrumented Redis lock object.
        :raises RuntimeError: If Redis is not available.
        """
        if self.is_available():
            # Locks are not versioned as they are not for caching
            redis_lock = self.redis.lock(name, timeout=timeout, blocking_timeout=blocking_timeout)
            return InstrumentedLock(redis_lock, name) # Wrap with InstrumentedLock
        
        # Fallback to DummyLock with instrumentation if Redis is not available
        dummy_lock = _DummyLock(name) # Pass name for consistency, though dummy_lock doesn't use it
        LOCK_ACQUISITION_ATTEMPTS_TOTAL.labels(lock_name=name, outcome="fallback_dummy").inc()
        return dummy_lock # Return dummy lock as before, now with instrumentation

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache. Deserializes JSON."""
        versioned_key = self._get_versioned_key(key)
        
        # 1. Try L0 (Local LRU)
        l0_val = self._lru.get(versioned_key)
        if l0_val is not None:
            return l0_val

        # 2. Try L1 (Redis)
        if self.is_available():
            try:
                value = self.redis.get(versioned_key)
                if value:
                    logger.debug(f"CACHE HIT for key: {versioned_key}")
                    data = json.loads(value)
                    self._lru.put(versioned_key, data) # Promote to L0
                    return data
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
        
        # Always update L0
        self._lru.put(versioned_key, value)

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
        self._lru.delete(versioned_key)

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
