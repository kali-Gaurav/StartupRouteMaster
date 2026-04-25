import logging
import time
from datetime import datetime, date
from typing import Dict, Any, Optional
from sqlalchemy import select, update, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.session import AsyncSessionTransit
from database.models import TrainRunningStatusCache
from core.redis_client import async_redis_client
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("service.ntes_sync")

class NtesSyncService:
    """
    Handles persistence and multi-layer caching for NTES scraped data.
    Ensures 'RouteMaster' has fast access to validated running status.
    """
    
    # Class-level resilience components
    _redis_circuit_breaker = circuit_breaker(
        name="ntes_sync_redis",
        failure_threshold=5,
        recovery_timeout=30.0
    )
    _db_circuit_breaker = circuit_breaker(
        name="ntes_sync_db",
        failure_threshold=5,
        recovery_timeout=60.0
    )
    _redis_retry_policy = retry_policy(
        max_attempts=3,
        strategy=RetryStrategy.LINEAR_BACKOFF,
        base_delay=0.1,
        max_delay=2.0
    )
    _db_retry_policy = retry_policy(
        max_attempts=3,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        base_delay=0.5,
        max_delay=10.0
    )
    _metrics = MetricsClient(
        service_name="ntes_sync_service",
        default_tags={"component": "scraper"}
    )
    _metrics.gauge("redis_circuit_breaker_state", lambda: _redis_circuit_breaker.state.value)
    _metrics.gauge("db_circuit_breaker_state", lambda: _db_circuit_breaker.state.value)
    _metrics.counter("upsert_requests_total")
    _metrics.counter("upsert_requests_success")
    _metrics.counter("upsert_requests_failed")
    _metrics.counter("get_cached_requests_total")
    _metrics.counter("get_cached_requests_hit")
    _metrics.counter("get_cached_requests_miss")
    _metrics.counter("get_cached_requests_failed")
    _metrics.histogram("upsert_duration_seconds")
    _metrics.histogram("get_cached_duration_seconds")

    @classmethod
    @track_metrics(service="ntes_sync_service", operation="upsert_status")
    @_redis_circuit_breaker
    @_redis_retry_policy
    async def upsert_status(cls, train_number: str, journey_date: date, data: Dict[str, Any]):
        """
        Upserts the scraped data into the database and updates Redis.
        [Task 48.9 & 48.10]
        """
        start_time = time.perf_counter()
        try:
            # 1. Update Redis (for extremely fast retrieval)
            cache_key = f"status:ntes:{train_number}:{journey_date.isoformat()}"
            await async_redis_client.setex(cache_key, 180, str(data)) # 3 Min TTL
            
            # 2. Update Database (for persistence and history)
            async with AsyncSessionTransit() as session:
                # PostgreSQL UPSERT logic
                stmt = pg_insert(TrainRunningStatusCache).values(
                    train_number=train_number,
                    journey_date=journey_date,
                    current_station=data.get("current_station", "N/A"),
                    delay_minutes=data.get("delay_minutes", 0),
                    running_status_text=data.get("delay_info", "N/A"),
                    data_payload=data.get("full_table", []),
                    last_updated_at=datetime.utcnow()
                ).on_conflict_do_update(
                    constraint="uix_train_date",
                    set_={
                        "current_station": data.get("current_station", "N/A"),
                        "delay_minutes": data.get("delay_minutes", 0),
                        "running_status_text": data.get("delay_info", "N/A"),
                        "data_payload": data.get("full_table", []),
                        "last_updated_at": datetime.utcnow()
                    }
                )
                
                await session.execute(stmt)
                await session.commit()
            
            duration = time.perf_counter() - start_time
            cls._metrics.histogram("upsert_duration_seconds", duration)
            cls._metrics.counter("upsert_requests_success", tags={"train_number": train_number})
            logger.info(f"✅ Synced status for {train_number} ({journey_date}) to DB and Cache in {duration:.3f}s")
            return True
        except Exception as e:
            duration = time.perf_counter() - start_time
            cls._metrics.histogram("upsert_duration_seconds", duration)
            cls._metrics.counter("upsert_requests_failed", tags={"error_type": type(e).__name__})
            logger.error(f"❌ Failed to sync NTES status for {train_number}: {e}")
            raise

    @classmethod
    @track_metrics(service="ntes_sync_service", operation="get_cached_status")
    @_redis_circuit_breaker
    @_redis_retry_policy
    async def get_cached_status(cls, train_number: str, journey_date: date) -> Optional[Dict[str, Any]]:
        """
        Retrieves status from Redis or Database if fresh enough (< 3 mins).
        """
        start_time = time.perf_counter()
        cache_key = f"status:ntes:{train_number}:{journey_date.isoformat()}"
        
        try:
            # 1. Check Redis
            cached_raw = await async_redis_client.get(cache_key)
            if cached_raw:
                try:
                    # Assuming data was stored as stringified dict
                    result = eval(cached_raw)
                    duration = time.perf_counter() - start_time
                    cls._metrics.histogram("get_cached_duration_seconds", duration)
                    cls._metrics.counter("get_cached_requests_hit", tags={"source": "redis"})
                    logger.debug(f"🔴 [NTES] Cache HIT for {train_number} in {duration:.3f}s")
                    return result
                except:
                    pass
            
            # 2. Check Database
            async with AsyncSessionTransit() as session:
                query = select(TrainRunningStatusCache).filter(
                    TrainRunningStatusCache.train_number == train_number,
                    TrainRunningStatusCache.journey_date == journey_date
                )
                result = await session.execute(query)
                status = result.scalar_one_or_none()
                
                if status:
                    # Only return if fresh enough (e.g., < 2 minutes)
                    age = (datetime.utcnow() - status.last_updated_at).total_seconds()
                    if age < 120:
                        response = {
                            "current_station": status.current_station,
                            "delay_info": status.running_status_text,
                            "delay_minutes": status.delay_minutes,
                            "full_table": status.data_payload,
                            "last_updated": status.last_updated_at.isoformat()
                        }
                        duration = time.perf_counter() - start_time
                        cls._metrics.histogram("get_cached_duration_seconds", duration)
                        cls._metrics.counter("get_cached_requests_hit", tags={"source": "database"})
                        logger.debug(f"🟡 [NTES] Cache HIT (DB) for {train_number} in {duration:.3f}s")
                        return response
            
            duration = time.perf_counter() - start_time
            cls._metrics.histogram("get_cached_duration_seconds", duration)
            cls._metrics.counter("get_cached_requests_miss")
            logger.debug(f"⚪ [NTES] Cache MISS for {train_number}")
            return None
        except Exception as e:
            duration = time.perf_counter() - start_time
            cls._metrics.histogram("get_cached_duration_seconds", duration)
            cls._metrics.counter("get_cached_requests_failed", tags={"error_type": type(e).__name__})
            logger.error(f"❌ Failed to get cached NTES status for {train_number}: {e}")
            raise

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "ntes_sync_service",
            "redis_circuit_breaker_state": cls._redis_circuit_breaker.state.name,
            "redis_circuit_breaker_failures": cls._redis_circuit_breaker.failure_count,
            "db_circuit_breaker_state": cls._db_circuit_breaker.state.name,
            "db_circuit_breaker_failures": cls._db_circuit_breaker.failure_count,
            "upsert_requests_total": cls._metrics.get_counter("upsert_requests_total"),
            "upsert_requests_success": cls._metrics.get_counter("upsert_requests_success"),
            "upsert_requests_failed": cls._metrics.get_counter("upsert_requests_failed"),
            "get_cached_requests_total": cls._metrics.get_counter("get_cached_requests_total"),
            "get_cached_requests_hit": cls._metrics.get_counter("get_cached_requests_hit"),
            "get_cached_requests_miss": cls._metrics.get_counter("get_cached_requests_miss"),
            "get_cached_requests_failed": cls._metrics.get_counter("get_cached_requests_failed"),
            "upsert_duration_p50": cls._metrics.get_percentile("upsert_duration_seconds", 50),
            "upsert_duration_p95": cls._metrics.get_percentile("upsert_duration_seconds", 95),
            "get_cached_duration_p50": cls._metrics.get_percentile("get_cached_duration_seconds", 50),
            "get_cached_duration_p95": cls._metrics.get_percentile("get_cached_duration_seconds", 95),
        }

    @classmethod
    def health_check(cls) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if (cls._redis_circuit_breaker.state == CircuitState.CLOSED and 
                                   cls._db_circuit_breaker.state == CircuitState.CLOSED) else "degraded",
            "service": "ntes_sync_service",
            "redis_circuit_breaker": cls._redis_circuit_breaker.state.name,
            "db_circuit_breaker": cls._db_circuit_breaker.state.name,
            "timestamp": datetime.utcnow().isoformat()
        }

    @classmethod
    def reset_circuit_breaker(cls, breaker_name: str = "all"):
        """Reset circuit breaker(s) to closed state."""
        if breaker_name == "all" or breaker_name == "redis":
            cls._redis_circuit_breaker.reset()
        if breaker_name == "all" or breaker_name == "db":
            cls._db_circuit_breaker.reset()
        logger.info(f"🔄 [NTES] Circuit breaker '{breaker_name}' reset")

ntes_sync_service = NtesSyncService()