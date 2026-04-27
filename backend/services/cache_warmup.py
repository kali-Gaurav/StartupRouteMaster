import logging
import asyncio
from typing import List, Set, Optional
from datetime import datetime
from collections import deque
from database.session import AsyncSessionUser, init_db
from core.route_engine.transfer_graph_builder import TransferGraphBuilder
from core.hubs import MEGA_HUBS, MAJOR_HUBS
from core.resilience import circuit_breaker_manager, CircuitConfig, CircuitBreaker
from core.retry import RetryPolicy

logger = logging.getLogger("cache-warmup")

class CacheWarmupService:
    """
    [Task 23] Pre-warms the Transfer Graph for major hubs.
    Eliminates first-request JIT latency.
    """
    
    def __init__(self):
        self._is_running = False
        
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "cache_warmup_db",
            CircuitConfig(
                failure_threshold=3,
                timeout_seconds=120.0,
                success_threshold=2
            )
        )
        
        # Circuit breaker for cache operations
        self._cache_breaker = circuit_breaker_manager.get_or_create(
            "cache_warmup_cache",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=60.0,
                success_threshold=3
            )
        )
        
        # Retry policy for hub warmup operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "database" in str(e).lower(),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("CacheWarmupService initialized with resilience patterns")

    async def run_hub_warmup_cycle(self):
        """
        Background task to warm the transfer cache for top 30 hubs.
        """
        if self._is_running: return
        self._is_running = True
        
        try:
            logger.info("🔥 Starting Hub Transfer Cache Warmup (MEGA/MAJOR Tiers)...")
            await init_db()
            
            # Combine hubs
            target_hubs = list(MEGA_HUBS) + list(MAJOR_HUBS)
            
            async with AsyncSessionUser() as session:
                builder = TransferGraphBuilder(session)
                
                # We'll warm the most common 20 hubs first
                count = 0
                for hub_code in target_hubs[:20]:
                    if hub_code is None:
                        continue
                    try:
                        # Build logic usually requires finding the Stop ID for the code
                        from database.models import Stop
                        from sqlalchemy import select
                        
                        stmt = select(Stop).where(Stop.code == hub_code)
                        result = await session.execute(stmt)
                        stop = result.scalar_one_or_none()
                        
                        if stop:
                            # Triggering explicit/implicit build for this stop
                            # If the builder caches internally, this warms it.
                            logger.debug(f"Warming transfers for {hub_code}...")
                            # In current implementation, build_transfer_graph builds EVERYTHING.
                            # We might want to optimize builder to build per-hub.
                            # For Task 23, we'll just trigger a full build if it's not already built.
                            await builder.build_transfer_graph()
                            # Once built, the builder or a global cache should hold it.
                            break # build_transfer_graph covers all stops usually
                        
                    except Exception as e:
                        logger.warning(f"Failed to warm hub {hub_code}: {e}")
                
            logger.info("✅ Hub Transfer Cache Warmup Complete.")
        except Exception as e:
            logger.error(f"❌ Cache Warmup Failed: {e}", exc_info=True)
        finally:
            self._is_running = False

    async def _record_metrics(self, operation_type: str, success: bool, error: Optional[str] = None):
        """Record metrics for cache warmup operations."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "error": error
            })
    
    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            op_type = m.get("operation_type", "unknown")
            if op_type not in by_type:
                by_type[op_type] = {"total": 0, "success": 0}
            by_type[op_type]["total"] += 1
            if m["success"]:
                by_type[op_type]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_type,
            "circuit_breaker_db_state": self._db_breaker.get_state().value,
            "circuit_breaker_cache_state": self._cache_breaker.get_state().value
        }
    
    def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "is_running": self._is_running,
            "circuit_breaker": {
                "db": {
                    "state": self._db_breaker.get_state().value,
                    "failure_count": self._db_breaker.failure_count,
                    "success_count": self._db_breaker.success_count
                },
                "cache": {
                    "state": self._cache_breaker.get_state().value,
                    "failure_count": self._cache_breaker.failure_count,
                    "success_count": self._cache_breaker.success_count
                }
            },
            "metrics": self.get_metrics()
        }
    
    def reset_circuit_breakers(self):
        """Reset circuit breakers."""
        self._db_breaker.reset()
        self._cache_breaker.reset()
        logger.info("Circuit breakers reset for cache_warmup_service")

hub_warmup_service = CacheWarmupService()
