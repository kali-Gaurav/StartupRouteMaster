import asyncio
import redis
from redis.lock import Lock
from redis.exceptions import RedisError
import json
import logging
import fnmatch
from typing import Optional, Any, Dict, List, Union, cast
import time # New: Import time for duration calculation
from collections import OrderedDict, deque
from datetime import datetime

from config import Config
from utils.metrics import LOCK_ACQUISITION_ATTEMPTS_TOTAL, LOCK_HOLD_DURATION_SECONDS # New: Import custom metrics
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy

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

    def release(self) -> None:
        if self._acquire_time:
            LOCK_HOLD_DURATION_SECONDS.labels(lock_name=self._name).observe(time.time() - self._acquire_time)
            self._acquire_time = None
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

class CacheServiceMetrics:
    """Metrics tracking for cache service."""

    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()

    async def record_cache_operation(self, operation: str, success: bool, duration_ms: float):
        """Record cache operation metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "success": success,
                "duration_ms": duration_ms
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}

        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_operation = {}
        for m in self._metrics:
            op = m["operation"]
            if op not in by_operation:
                by_operation[op] = {"total": 0, "success": 0}
            by_operation[op]["total"] += 1
            if m["success"]:
                by_operation[op]["success"] += 1

        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "by_operation": by_operation
        }


class CacheService:
    """A Redis-based caching service with an in-process fallback for tests/dev when Redis is not available."""

    def __init__(self, redis_url: str = Config.REDIS_URL):
        self._in_memory: Dict[str, Any] = {}
        self._lru = LocalLRU(capacity=500) # L0 Local Cache
        self.version_prefix = Config.REDIS_VERSION_PREFIX
        self.redis: Optional[redis.Redis] = None

        # Circuit breaker for Redis operations
        self._redis_breaker = circuit_breaker_manager.get_or_create(
            "cache_redis",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )

        # Retry policy for Redis operations
        self._redis_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=2.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )

        # Metrics tracking
        self._metrics = CacheServiceMetrics()

        try:
            if not redis_url:
                raise ValueError("REDIS_URL is not set")
            # Note: decode_responses=True is important for locks and general use
            self.redis = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None, socket_timeout=3.0, socket_connect_timeout=3.0)
            self.redis.ping()
            logger.info("Successfully connected to Redis.")
        except Exception as e:
            logger.warning(f"Could not connect to Redis (falling back to in-memory cache): {e}")
            self.redis = None

        logger.info("CacheService initialized with resilience patterns")

    def _get_versioned_key(self, key: str) -> str:
        """Prepends the version prefix to the key."""
        return f"{self.version_prefix}:{key}"

    def is_available(self) -> bool:
        """Check if the Redis connection is available."""
        return self.redis is not None

    def get_lock(self, name: str, timeout: int = 10, blocking_timeout: int = 0) -> Union[InstrumentedLock, _DummyLock]:
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
            redis_client = self.redis
            assert redis_client is not None
            redis_lock = redis_client.lock(name, timeout=timeout, blocking_timeout=blocking_timeout)
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
                redis_client = self.redis
                assert redis_client is not None
                value = redis_client.get(versioned_key)
                if value:
                    logger.debug(f"CACHE HIT for key: {versioned_key}")
                    data = json.loads(cast(str, value))
                    self._lru.put(versioned_key, data) # Promote to L0
                    return data
                else:
                    logger.debug(f"CACHE MISS for key: {versioned_key}")
                    return None
            except (RedisError, json.JSONDecodeError) as e:
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
                redis_client = self.redis
                assert redis_client is not None
                serialized_value = json.dumps(value)
                redis_client.set(versioned_key, serialized_value, ex=ttl_seconds)
                logger.debug(f"CACHE SET for key: {versioned_key} with TTL: {ttl_seconds}s")
            except (RedisError, TypeError) as e:
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
                redis_client = self.redis
                assert redis_client is not None
                redis_client.delete(versioned_key)
                logger.debug(f"CACHE DELETE for key: {versioned_key}")
            except RedisError as e:
                logger.error(f"Failed to delete key {versioned_key} from cache: {e}")
            return

        self._in_memory.pop(versioned_key, None)
        logger.debug(f"IN-MEM CACHE DELETE for key: {versioned_key}")

    def get_pattern(self, pattern: str) -> Dict[str, Any]:
        """Return all cache entries whose versioned key matches the provided pattern."""
        versioned_pattern = self._get_versioned_key(pattern)
        results: Dict[str, Any] = {}

        if self.is_available():
            try:
                redis_client = self.redis
                assert redis_client is not None
                keys = cast(List[str], redis_client.keys(versioned_pattern))
                for key in keys or []:
                    value = redis_client.get(key)
                    if value is None:
                        continue
                    try:
                        results[key[len(self.version_prefix) + 1:]] = json.loads(cast(str, value))
                    except json.JSONDecodeError:
                        results[key[len(self.version_prefix) + 1:]] = value
                return results
            except RedisError as e:
                logger.error(f"Failed to fetch pattern {versioned_pattern} from cache: {e}")
                return {}

        for key, value in self._in_memory.items():
            if fnmatch.fnmatch(key, versioned_pattern):
                results[key[len(self.version_prefix) + 1:]] = value
        return results

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a cache counter in Redis or fallback store."""
        versioned_key = self._get_versioned_key(key)
        if self.is_available():
            try:
                redis_client = self.redis
                assert redis_client is not None
                return int(cast(Union[int, str], redis_client.incr(versioned_key, amount)))
            except RedisError as e:
                logger.error(f"Failed to increment cache key {versioned_key}: {e}")
                return 0

        current = int(self._in_memory.get(versioned_key, 0))
        current += amount
        self._in_memory[versioned_key] = current
        return current

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        """Set TTL for a cache key when Redis is available."""
        versioned_key = self._get_versioned_key(key)
        if self.is_available():
            try:
                redis_client = self.redis
                assert redis_client is not None
                return bool(cast(Any, redis_client.expire(versioned_key, ttl_seconds)))
            except RedisError as e:
                logger.error(f"Failed to set expiry for cache key {versioned_key}: {e}")
                return False
        return False

    # [32.1] Brute-Force Rate Limiting
    def record_failed_login(self, ip: str):
        """Increments failure count for an IP. Sets 5-min TTL."""
        if not self.is_available(): return
        redis_client = self.redis
        assert redis_client is not None
        key = f"login_fails:{ip}"
        try:
            count = cast(Union[int, str], redis_client.incr(key))
            if int(count) == 1:
                redis_client.expire(key, 300) # 5 minutes
            return int(count)
        except RedisError:
            return 0

    def is_ip_blocked(self, ip: str) -> bool:
        """Checks if an IP has exceeded 10 failures."""
        if not self.is_available(): return False
        redis_client = self.redis
        assert redis_client is not None
        key = f"login_fails:{ip}"
        try:
            count = int(cast(Union[int, str], redis_client.get(key) or 0))
            return count >= 10
        except: return False

    async def get_metrics(self) -> dict:
        """Get service metrics."""
        return self._metrics.get_metrics()

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy" if self.is_available() else "degraded",
            "redis_available": self.is_available(),
            "circuit_breaker": self._redis_breaker.get_metrics(),
            "metrics": self._metrics.get_metrics()
        }

    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self._redis_breaker.reset()
        logger.info("All circuit breakers reset for cache_service")

# Global instance to be used across the application
cache_service = CacheService()
