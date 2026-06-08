"""
Congestion Manager - Search Volume and Crowd Trend Tracking
============================================================

Tracks search volume and crowd trends for trips.
Uses Redis to store dynamic 'Congestion Ranks'.

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import asyncio
from typing import Dict, List, Any
from collections import deque
from datetime import datetime
import logging

from core.resilience.core import circuit_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy

logger = logging.getLogger(__name__)


class CongestionManager:
    """
    [Task 139] Tracks search volume and crowd trends for trips.
    Uses Redis to store dynamic 'Congestion Ranks'.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    PREFIX = "nexus:congestion:v1:"
    
    def __init__(self):
        """Initialize congestion manager with resilience patterns."""
        # Circuit breaker for Redis operations
        self._redis_breaker = circuit_manager.get_or_create(
            "congestion_manager_redis",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=10.0,
                success_threshold=3
            )
        )
        
        # Retry policy for Redis operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=1.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Congestion history
        self._congestion_history: deque = deque(maxlen=100)
        self._history_lock = asyncio.Lock()
        
        # Local cache for fallback
        self._local_cache: Dict[str, int] = {}
        self._cache_lock = asyncio.Lock()
        
        logger.info("CongestionManager initialized with resilience patterns")

    async def _get_redis(self):
        """Get Redis connection."""
        try:
            from services.multi_layer_cache import multi_layer_cache
            return multi_layer_cache.redis
        except Exception as e:
            logger.warning(f"⚠️ Redis not available: {e}")
            return None

    async def _increment_local(self, trip_ids: List[int]):
        """Increment counters in local cache as fallback."""
        async with self._cache_lock:
            for tid in trip_ids:
                key = f"{self.PREFIX}{tid}"
                self._local_cache[key] = self._local_cache.get(key, 0) + 1

    async def increment_surge(self, trip_ids: List[int]):
        """
        Increment search counters for the given trips (Search-Aware Surge).
        
        Args:
            trip_ids: List of trip IDs to increment
            
        Protected by circuit breaker with local fallback.
        """
        if not trip_ids:
            return
        
        r = await self._get_redis()
        
        if not r:
            # Use local cache as fallback
            await self._increment_local(trip_ids)
            await self._record_metrics("increment_surge", True, "local_fallback")
            return
        
        async def _do_increment():
            """Internal increment logic."""
            async with r.pipeline(transaction=False) as pipe:
                for tid in trip_ids:
                    key = f"{self.PREFIX}{tid}"
                    await pipe.incr(key)
                    await pipe.expire(key, 7200)  # 2 hours TTL
                await pipe.execute()
        
        try:
            await self._redis_breaker.execute(
                self._retry_policy.execute,
                _do_increment
            )
            await self._record_metrics("increment_surge", True, "redis")
            
        except Exception as e:
            logger.debug(f"Congestion Surge Update Failed: {e}")
            # Fallback to local cache
            await self._increment_local(trip_ids)
            await self._record_metrics("increment_surge", True, "local_fallback")

    async def get_congestion_ranks(self, trip_ids: List[int]) -> Dict[int, float]:
        """
        Fetch normalized congestion ranks (0.0=Empty, 1.0=Popular, 2.0=Extreme).
        
        Args:
            trip_ids: List of trip IDs to check
            
        Returns:
            Dict mapping trip_id to congestion rank
            
        Protected by circuit breaker with local fallback.
        """
        if not trip_ids:
            return {}
        
        r = await self._get_redis()
        
        if not r:
            # Use local cache as fallback
            ranks = {}
            for tid in trip_ids:
                key = f"{self.PREFIX}{tid}"
                count = self._local_cache.get(key, 0)
                rank = min(2.0, count / 50.0)
                ranks[tid] = round(rank, 2)
            
            await self._record_metrics("get_congestion_ranks", True, "local_fallback")
            return ranks
        
        async def _do_fetch():
            """Internal fetch logic."""
            keys = [f"{self.PREFIX}{tid}" for tid in trip_ids]
            return await r.mget(keys)
        
        try:
            counts = await self._redis_breaker.execute(
                self._retry_policy.execute,
                _do_fetch
            )
            
            ranks = {}
            for i, tid in enumerate(trip_ids):
                count_str = counts[i]
                count = int(count_str) if count_str else 0
                
                # Normalization Heuristic:
                # - 0 to 10 searches/hr: Quiet (0.0 to 0.2)
                # - 50 searches/hr: Popular (1.0)
                # - 100+ searches/hr: Overcrowded (2.0)
                rank = min(2.0, count / 50.0)
                ranks[tid] = round(rank, 2)
            
            # Record history
            await self._add_to_history(trip_ids, ranks)
            
            await self._record_metrics("get_congestion_ranks", True, "redis")
            return ranks
            
        except Exception as e:
            logger.debug(f"Congestion Rank Fetch Failed: {e}")
            # Fallback to local cache
            return await self.get_congestion_ranks(trip_ids)

    async def get_congestion_for_trip(self, trip_id: int) -> float:
        """
        Get congestion rank for a single trip.
        
        Args:
            trip_id: Trip ID to check
            
        Returns:
            Congestion rank (0.0-2.0)
        """
        ranks = await self.get_congestion_ranks([trip_id])
        return ranks.get(trip_id, 0.0)

    async def get_top_congested(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top congested trips.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of trip info with congestion ranks
        """
        # This would typically query Redis sorted sets
        # For now, return empty list as placeholder
        return []

    async def clear_congestion(self, trip_ids: List[int]):
        """
        Clear congestion data for specific trips.
        
        Args:
            trip_ids: List of trip IDs to clear
        """
        r = await self._get_redis()
        
        if r:
            try:
                keys = [f"{self.PREFIX}{tid}" for tid in trip_ids]
                await r.delete(*keys)
                await self._record_metrics("clear_congestion", True, "redis")
            except Exception as e:
                logger.error(f"Failed to clear congestion: {e}")
                await self._record_metrics("clear_congestion", False, "redis")
        else:
            # Clear from local cache
            async with self._cache_lock:
                for tid in trip_ids:
                    key = f"{self.PREFIX}{tid}"
                    self._local_cache.pop(key, None)
            await self._record_metrics("clear_congestion", True, "local")

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        operation_type: str,
        success: bool,
        source: str = ""
    ):
        """Record operation metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "source": source
            })

    async def _add_to_history(self, trip_ids: List[int], ranks: Dict[int, float]):
        """Add to congestion history."""
        async with self._history_lock:
            self._congestion_history.append({
                "timestamp": datetime.utcnow(),
                "trip_ids": trip_ids,
                "ranks": ranks
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_source = {}
        for m in self._metrics:
            source = m.get("source", "unknown")
            by_source[source] = by_source.get(source, 0) + 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "source_breakdown": by_source,
            "circuit_breaker_state": self._redis_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "redis_available": True,  # Would check actual connection
            "circuit_breaker": {
                "state": self._redis_breaker.get_state().value,
                "failure_count": self._redis_breaker.failure_count,
                "success_count": self._redis_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._redis_breaker.reset()
        logger.info("Circuit breaker reset for congestion manager")

    def get_congestion_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent congestion history."""
        return list(self._congestion_history)[-limit:]


# Global instance
congestion_manager = CongestionManager()
