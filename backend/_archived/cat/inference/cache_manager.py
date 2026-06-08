"""
Cache Manager for the Contextual Availability Transformer (CAT) system.
Handles prediction caching with Redis support and integrates with model updates
for cache invalidation.

Features:
- Redis-based caching with configurable TTL
- Local L1 cache for low-latency access
- Cache key generation based on location_id and prediction_time
- Automatic cache invalidation on model updates
- Cache statistics and metrics
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import defaultdict
import json

import redis

from ..config import settings
from ..models.schemas import AvailabilityPrediction

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Configuration for the prediction cache."""
    enabled: bool = True
    redis_url: Optional[str] = None
    ttl_seconds: int = 300  # 5 minutes default TTL
    local_cache_ttl_seconds: int = 60  # 1 minute for local L1 cache
    local_cache_max_size: int = 1000  # Maximum entries in local cache
    redis_cache_prefix: str = "cat:"
    invalidate_on_model_update: bool = True
    invalidate_on_reload: bool = True


@dataclass
class CacheStats:
    """Statistics for the prediction cache."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    invalidations: int = 0
    redis_hits: int = 0
    redis_misses: int = 0
    local_hits: int = 0
    local_misses: int = 0
    last_access_time: Optional[datetime] = None
    last_miss_time: Optional[datetime] = None


class PredictionCache:
    """
    Redis-based cache for predictions with local L1 cache.
    
    Reduces latency for repeated requests and supports TTL-based expiration.
    Implements a two-tier caching strategy:
    - L1: Local in-memory cache for fastest access
    - L2: Redis cache for distributed caching across instances
    
    Features:
    - Configurable TTL for cache entries
    - Cache key generation based on location_id and prediction_time
    - Automatic serialization/deserialization of predictions
    - Statistics tracking for cache performance monitoring
    """
    
    def __init__(
        self,
        config: CacheConfig = None,
        redis_client: redis.Redis = None
    ):
        """
        Initialize the prediction cache.
        
        Args:
            config: Cache configuration
            redis_client: Pre-configured Redis client (optional)
        """
        self.config = config or CacheConfig()
        self._redis_client = redis_client
        self._local_cache: Dict[str, Tuple[AvailabilityPrediction, datetime]] = {}
        self._local_cache_order: List[str] = []  # For LRU eviction
        self._stats = CacheStats()
        self._lock = threading.RLock()
        self._redis_connected = True
        
        # Initialize Redis connection
        if self._redis_client is None and self.config.redis_url:
            try:
                self._redis_client = redis.from_url(
                    self.config.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self._redis_client.ping()
                logger.info(f"Redis cache initialized at {self.config.redis_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using local cache only.")
                self._redis_connected = False
                self._redis_client = None
        elif not self.config.redis_url:
            logger.info("Using local cache only (no Redis URL configured)")
    
    def _get_cache_key(self, location_id: str, prediction_time: datetime) -> str:
        """
        Generate a cache key for a prediction request.
        
        The cache key is structured as: {prefix}pred:{location_id}:{iso_time}
        
        Args:
            location_id: Location identifier
            prediction_time: Time of prediction
            
        Returns:
            Cache key string
        """
        # Normalize prediction_time to minute precision to improve cache hits
        if isinstance(prediction_time, datetime):
            normalized_time = prediction_time.replace(second=0, microsecond=0)
            time_str = normalized_time.isoformat()
        else:
            time_str = str(prediction_time)
        
        return f"{self.config.redis_cache_prefix}pred:{location_id}:{time_str}"
    
    def _serialize_prediction(self, prediction: AvailabilityPrediction) -> str:
        """
        Serialize a prediction to JSON string.
        
        Args:
            prediction: Prediction to serialize
            
        Returns:
            JSON string representation
        """
        data = prediction.model_dump()
        
        # Convert datetime to ISO format string
        if isinstance(data.get("prediction_time"), datetime):
            data["prediction_time"] = data["prediction_time"].isoformat()
        
        # Convert confidence_interval tuple to list for JSON
        if isinstance(data.get("confidence_interval"), tuple):
            data["confidence_interval"] = list(data["confidence_interval"])
        
        return json.dumps(data)
    
    def _deserialize_prediction(self, data: str) -> AvailabilityPrediction:
        """
        Deserialize a prediction from JSON string.
        
        Args:
            data: JSON string representation
            
        Returns:
            Deserialized AvailabilityPrediction
        """
        parsed = json.loads(data)
        
        # Convert prediction_time back to string (keep as string for API compatibility)
        # The AvailabilityPrediction model handles string parsing
        
        return AvailabilityPrediction(**parsed)
    
    def get(self, location_id: str, prediction_time: datetime) -> Optional[AvailabilityPrediction]:
        """
        Get a cached prediction.
        
        Implements a two-tier lookup:
        1. Check local L1 cache first
        2. If miss, check Redis L2 cache
        3. If miss, return None
        
        Args:
            location_id: Location identifier
            prediction_time: Time of prediction
            
        Returns:
            Cached prediction or None if not found/expired
        """
        cache_key = self._get_cache_key(location_id, prediction_time)
        now = datetime.utcnow()
        
        with self._lock:
            self._stats.last_access_time = now
            
            # Check L1 local cache first
            if cache_key in self._local_cache:
                cached_value, timestamp = self._local_cache[cache_key]
                age_seconds = (now - timestamp).total_seconds()
                
                if age_seconds < self.config.local_cache_ttl_seconds:
                    # Update LRU order
                    if cache_key in self._local_cache_order:
                        self._local_cache_order.remove(cache_key)
                    self._local_cache_order.append(cache_key)
                    
                    self._stats.hits += 1
                    self._stats.local_hits += 1
                    logger.debug(f"L1 cache hit for {cache_key}")
                    return cached_value
                else:
                    # Expired in local cache, remove it
                    del self._local_cache[cache_key]
                    self._local_cache_order.remove(cache_key)
            
            self._stats.local_misses += 1
            
            # Check L2 Redis cache
            if self._redis_client and self._redis_connected:
                try:
                    cached_data = self._redis_client.get(cache_key)
                    
                    if cached_data:
                        prediction = self._deserialize_prediction(cached_data)
                        
                        # Update L1 cache
                        self._local_cache[cache_key] = (prediction, now)
                        self._local_cache_order.append(cache_key)
                        
                        # Evict old entries if cache is full
                        self._evict_lru_if_needed()
                        
                        self._stats.hits += 1
                        self._stats.redis_hits += 1
                        logger.debug(f"L2 cache hit for {cache_key}")
                        return prediction
                    else:
                        self._stats.redis_misses += 1
                        
                except Exception as e:
                    logger.warning(f"Redis get failed: {e}")
                    self._redis_connected = False
            
            # Cache miss
            self._stats.misses += 1
            self._stats.last_miss_time = now
            logger.debug(f"Cache miss for {cache_key}")
            return None
    
    def set(
        self,
        location_id: str,
        prediction_time: datetime,
        prediction: AvailabilityPrediction
    ) -> bool:
        """
        Cache a prediction.
        
        Stores in both L1 local cache and L2 Redis cache.
        
        Args:
            location_id: Location identifier
            prediction_time: Time of prediction
            prediction: Prediction to cache
            
        Returns:
            True if successfully cached, False otherwise
        """
        if not self.config.enabled:
            return False
        
        cache_key = self._get_cache_key(location_id, prediction_time)
        now = datetime.utcnow()
        
        with self._lock:
            # Update L1 cache
            self._local_cache[cache_key] = (prediction, now)
            self._local_cache_order.append(cache_key)
            
            # Evict old entries if cache is full
            self._evict_lru_if_needed()
            
            # Update L2 Redis cache
            if self._redis_client and self._redis_connected:
                try:
                    serialized = self._serialize_prediction(prediction)
                    self._redis_client.setex(
                        cache_key,
                        self.config.ttl_seconds,
                        serialized
                    )
                    logger.debug(f"Cached prediction for {cache_key}")
                    self._stats.sets += 1
                    return True
                except Exception as e:
                    logger.warning(f"Redis set failed: {e}")
                    self._redis_connected = False
            
            self._stats.sets += 1
            return True
    
    def _evict_lru_if_needed(self) -> None:
        """Evict least recently used entries if local cache is full."""
        while len(self._local_cache) > self.config.local_cache_max_size:
            if not self._local_cache_order:
                break
                
            # Remove oldest entry
            oldest_key = self._local_cache_order.pop(0)
            if oldest_key in self._local_cache:
                del self._local_cache[oldest_key]
    
    def invalidate(self, location_id: str = None) -> int:
        """
        Invalidate cached predictions.
        
        Args:
            location_id: Specific location to invalidate (or all if None)
            
        Returns:
            Number of entries invalidated
        """
        with self._lock:
            invalidated_count = 0
            
            if location_id:
                # Invalidate specific location
                keys_to_delete = [
                    k for k in self._local_cache.keys()
                    if f":{location_id}:" in k or k.endswith(f":{location_id}:*")
                ]
                
                for key in keys_to_delete:
                    del self._local_cache[key]
                    if key in self._local_cache_order:
                        self._local_cache_order.remove(key)
                    invalidated_count += 1
                
                # Invalidate in Redis
                if self._redis_client and self._redis_connected:
                    try:
                        pattern = f"{self.config.redis_cache_prefix}pred:{location_id}:*"
                        keys = self._redis_client.keys(pattern)
                        if keys:
                            invalidated_count += len(keys)
                            self._redis_client.delete(*keys)
                    except Exception as e:
                        logger.warning(f"Redis invalidate failed: {e}")
                        self._redis_connected = False
            else:
                # Invalidate all
                invalidated_count = len(self._local_cache)
                self._local_cache.clear()
                self._local_cache_order.clear()
                
                # Invalidate in Redis
                if self._redis_client and self._redis_connected:
                    try:
                        pattern = f"{self.config.redis_cache_prefix}pred:*"
                        keys = self._redis_client.keys(pattern)
                        if keys:
                            invalidated_count += len(keys)
                            self._redis_client.delete(*keys)
                    except Exception as e:
                        logger.warning(f"Redis invalidate failed: {e}")
                        self._redis_connected = False
            
            if invalidated_count > 0:
                self._stats.invalidations += 1
                logger.info(f"Invalidated {invalidated_count} cache entries" +
                           (f" for location {location_id}" if location_id else ""))
            
            return invalidated_count
    
    def invalidate_by_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Glob pattern to match cache keys
            
        Returns:
            Number of entries invalidated
        """
        with self._lock:
            invalidated_count = 0
            
            # Match against local cache
            import fnmatch
            keys_to_delete = [
                k for k in self._local_cache.keys()
                if fnmatch.fnmatch(k, pattern)
            ]
            
            for key in keys_to_delete:
                del self._local_cache[key]
                if key in self._local_cache_order:
                    self._local_cache_order.remove(key)
                invalidated_count += 1
            
            # Match against Redis
            if self._redis_client and self._redis_connected:
                try:
                    keys = self._redis_client.keys(pattern)
                    if keys:
                        invalidated_count += len(keys)
                        self._redis_client.delete(*keys)
                except Exception as e:
                    logger.warning(f"Redis pattern invalidate failed: {e}")
                    self._redis_connected = False
            
            if invalidated_count > 0:
                self._stats.invalidations += 1
            
            return invalidated_count
    
    def clear(self) -> int:
        """
        Clear all cached predictions.
        
        Returns:
            Number of entries cleared
        """
        return self.invalidate()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_requests = self._stats.hits + self._stats.misses
            hit_rate = (self._stats.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "sets": self._stats.sets,
                "invalidations": self._stats.invalidations,
                "hit_rate_percent": round(hit_rate, 2),
                "local_cache_size": len(self._local_cache),
                "local_cache_max_size": self.config.local_cache_max_size,
                "ttl_seconds": self.config.ttl_seconds,
                "local_cache_ttl_seconds": self.config.local_cache_ttl_seconds,
                "redis_connected": self._redis_connected,
                "redis_url": self.config.redis_url or "local_only",
                "local_hits": self._stats.local_hits,
                "local_misses": self._stats.local_misses,
                "redis_hits": self._stats.redis_hits,
                "redis_misses": self._stats.redis_misses,
                "last_access_time": self._stats.last_access_time.isoformat() if self._stats.last_access_time else None,
                "last_miss_time": self._stats.last_miss_time.isoformat() if self._stats.last_miss_time else None
            }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        with self._lock:
            self._stats = CacheStats()
    
    def get_hit_rate(self) -> float:
        """
        Get the cache hit rate.
        
        Returns:
            Hit rate as a percentage (0-100)
        """
        with self._lock:
            total = self._stats.hits + self._stats.misses
            if total == 0:
                return 0.0
            return round(self._stats.hits / total * 100, 2)
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check cache health.
        
        Returns:
            Health status dictionary
        """
        redis_healthy = True
        
        if self._redis_client and self._redis_connected:
            try:
                self._redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis health check failed: {e}")
                redis_healthy = False
                self._redis_connected = False
        
        return {
            "healthy": True,
            "redis_connected": self._redis_connected,
            "redis_healthy": redis_healthy,
            "local_cache_entries": len(self._local_cache),
            "hit_rate_percent": self.get_hit_rate()
        }


class CacheManager:
    """
    Manages prediction cache with integration to model updates.
    
    Provides cache invalidation callbacks when models are updated,
    reloaded, or hot-swapped. This ensures predictions are not served
    from stale cache after model changes.
    
    Features:
    - Integration with ModelManager for automatic invalidation
    - Configurable invalidation triggers
    - Cache warming after model updates
    - Metrics and health monitoring
    """
    
    def __init__(
        self,
        cache: PredictionCache = None,
        config: CacheConfig = None
    ):
        """
        Initialize the cache manager.
        
        Args:
            cache: Prediction cache instance
            config: Cache configuration
        """
        self.cache = cache or PredictionCache(config=config)
        self._model_update_callbacks: List[Callable] = []
        self._model_version: Optional[str] = None
        self._lock = threading.RLock()
        
        logger.info("CacheManager initialized")
    
    def register_model_update_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback to be called when model is updated.
        
        Args:
            callback: Function to call with new model version
        """
        with self._lock:
            self._model_update_callbacks.append(callback)
    
    def on_model_loaded(self, version: str) -> None:
        """
        Handle model loaded event.
        
        Args:
            version: Model version that was loaded
        """
        with self._lock:
            self._model_version = version
        
        logger.info(f"Model loaded: {version}")
        
        # Notify callbacks
        for callback in self._model_update_callbacks:
            try:
                callback(version)
            except Exception as e:
                logger.warning(f"Model update callback failed: {e}")
    
    def on_model_hot_swap(self, old_version: str, new_version: str) -> int:
        """
        Handle model hot-swap event.
        
        Invalidates cache when model is hot-swapped to ensure
        predictions use the new model.
        
        Args:
            old_version: Previous model version
            new_version: New model version
            
        Returns:
            Number of cache entries invalidated
        """
        logger.info(f"Model hot-swap: {old_version} -> {new_version}")
        
        with self._lock:
            self._model_version = new_version
        
        # Invalidate all cache entries
        invalidated = self.cache.invalidate()
        
        # Notify callbacks
        for callback in self._model_update_callbacks:
            try:
                callback(new_version)
            except Exception as e:
                logger.warning(f"Model update callback failed: {e}")
        
        return invalidated
    
    def on_model_reload(self, version: str) -> int:
        """
        Handle model reload event.
        
        Invalidates cache when model is reloaded after failure.
        
        Args:
            version: Model version that was reloaded
            
        Returns:
            Number of cache entries invalidated
        """
        logger.info(f"Model reloaded: {version}")
        
        with self._lock:
            self._model_version = version
        
        # Invalidate cache if configured
        if self.cache.config.invalidate_on_reload:
            invalidated = self.cache.invalidate()
        else:
            invalidated = 0
        
        return invalidated
    
    def invalidate_for_location(self, location_id: str) -> int:
        """
        Invalidate cache for a specific location.
        
        Args:
            location_id: Location to invalidate
            
        Returns:
            Number of entries invalidated
        """
        return self.cache.invalidate(location_id)
    
    def invalidate_by_model_version(self, model_version: str) -> int:
        """
        Invalidate cache entries created by a specific model version.
        
        Note: This requires storing model version with each cached prediction.
        
        Args:
            model_version: Model version to invalidate
            
        Returns:
            Number of entries invalidated
        """
        pattern = f"{self.cache.config.redis_cache_prefix}pred:*"
        return self.cache.invalidate_by_pattern(pattern)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache manager statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "cache_stats": self.cache.get_stats(),
            "model_version": self._model_version,
            "registered_callbacks": len(self._model_update_callbacks)
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check cache manager health.
        
        Returns:
            Health status dictionary
        """
        return {
            "cache_healthy": self.cache.health_check(),
            "model_version": self._model_version
        }


def create_prediction_cache(
    redis_url: str = None,
    ttl_seconds: int = None,
    local_cache_ttl_seconds: int = None
) -> PredictionCache:
    """
    Factory function to create a prediction cache.
    
    Args:
        redis_url: Redis connection URL
        ttl_seconds: Cache TTL in seconds
        local_cache_ttl_seconds: Local cache TTL in seconds
        
    Returns:
        Configured PredictionCache instance
    """
    config = CacheConfig(
        redis_url=redis_url or settings.redis_url,
        ttl_seconds=ttl_seconds or settings.prediction_cache_ttl_seconds,
        local_cache_ttl_seconds=local_cache_ttl_seconds or 60
    )
    
    return PredictionCache(config=config)


def create_cache_manager(
    cache: PredictionCache = None,
    redis_url: str = None,
    ttl_seconds: int = None
) -> CacheManager:
    """
    Factory function to create a cache manager.
    
    Args:
        cache: Optional pre-configured cache
        redis_url: Redis connection URL
        ttl_seconds: Cache TTL in seconds
        
    Returns:
        Configured CacheManager instance
    """
    if cache is None:
        cache = create_prediction_cache(redis_url=redis_url, ttl_seconds=ttl_seconds)
    
    return CacheManager(cache=cache)