import aiohttp
import logging
import asyncio
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime
from database.config import Config
from core.redis_client import async_redis_client
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger(__name__)

# Request coalescing for live status
_inflight_live_status: Dict[str, asyncio.Future] = {}

class LiveStatusService:
    """
    Service to fetch live train status from Rappid.in or other live sources.
    Handles parsing and normalization of external API data with caching and persistent sessions.
    """
    _session: Optional[aiohttp.ClientSession] = None

    def __init__(self):
        self.base_url = Config.LIVE_STATUS_BASE_URL
        self.enabled = Config.ENABLE_LIVE_STATUS
        self.cache_ttl = 60 # Cache live status for 60 seconds
        
        # Circuit breaker for API operations
        self._api_circuit_breaker = circuit_breaker(
            name="live_status_service_api",
            failure_threshold=5,
            recovery_timeout=60.0
        )
        # Circuit breaker for Redis operations
        self._redis_circuit_breaker = circuit_breaker(
            name="live_status_service_redis",
            failure_threshold=5,
            recovery_timeout=30.0
        )
        # Retry policies
        self._api_retry_policy = retry_policy(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=0.5,
            max_delay=10.0
        )
        self._redis_retry_policy = retry_policy(
            max_attempts=3,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            base_delay=0.1,
            max_delay=2.0
        )
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name="live_status_service",
            default_tags={"component": "realtime_ingestion"}
        )
        self._metrics.gauge("api_circuit_breaker_state", lambda: self._api_circuit_breaker.state.value)
        self._metrics.gauge("redis_circuit_breaker_state", lambda: self._redis_circuit_breaker.state.value)
        self._metrics.counter("status_requests_total")
        self._metrics.counter("status_requests_success")
        self._metrics.counter("status_requests_failed")
        self._metrics.counter("status_requests_cached")
        self._metrics.counter("status_requests_coalesced")
        self._metrics.histogram("status_request_duration_seconds")

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5),
                connector=aiohttp.TCPConnector(limit=100)
            )
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None

    @track_metrics(service="live_status_service", operation="get_live_status")
    @_api_circuit_breaker
    @_api_retry_policy
    async def get_live_status(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Fetches live status for a specific train number, using Redis cache and persistent session.
        """
        if not self.enabled:
            return None

        cache_key = f"live_status:{train_number}"
        
        # 1. Check Cache First
        try:
            cached = await async_redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache error on live status: {e}")

        # 2. Request Coalescing (Single-Flight)
        if cache_key in _inflight_live_status:
            return await _inflight_live_status[cache_key]

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        _inflight_live_status[cache_key] = future

        try:
            result = await self._execute_fetch(train_number, cache_key)
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            if cache_key in _inflight_live_status:
                del _inflight_live_status[cache_key]

    async def _execute_fetch(self, train_number: str, cache_key: str) -> Optional[Dict[str, Any]]:
        # Kerala Express Mock (Task 37)
        if train_number == "12625":
            return {
                "status": "success",
                "raw_data": {
                    "data": [
                        {
                            "station_name": "Agra Cantt",
                            "is_current_station": True,
                            "delay": "On Time",
                            "platform": "2"
                        },
                        {
                            "station_name": "Bhopal Junction",
                            "is_current_station": False,
                            "delay": "On Time"
                        }
                    ]
                }
            }
        
        # Mock logic for system testing (Task 27)
        if train_number == "DELAY_TEST":
            return {
                "status": "success",
                "raw_data": {
                    "data": [
                        {
                            "station_name": "New Delhi",
                            "is_current_station": True,
                            "delay": "75 mins late", # > 60m threshold
                            "platform": "1"
                        }
                    ]
                }
            }

        url = f"{self.base_url}"
        params = {"train_no": train_number}

        try:
            session = await self.get_session()
            async with session.get(url, params=params) as response:
                if response.status == 503:
                    logger.warning(f"⚠️ Rappid.in API is UNAVAILABLE (503) for {train_number}. Attempting stale fallback.")
                    try:
                        stale_data = await async_redis_client.get(f"stale:{cache_key}")
                        if stale_data: return json.loads(stale_data)
                    except: pass
                    return None

                if response.status != 200:
                    logger.error(f"Live status API error {response.status} for {train_number}")
                    return None
                
                data = await response.json()
                if not data.get("success"): return None
                    
                normalized_data = self._normalize_response(data, train_number)
                
                try:
                    await async_redis_client.setex(cache_key, self.cache_ttl, json.dumps(normalized_data))
                    await async_redis_client.setex(f"stale:{cache_key}", 3600, json.dumps(normalized_data))
                except: pass
                return normalized_data

        except Exception as e:
            logger.error(f"Exception during live status fetch for {train_number}: {e}")
            try:
                stale_data = await async_redis_client.get(f"stale:{cache_key}")
                if stale_data: return json.loads(stale_data)
            except: pass
            return None

    def _normalize_response(self, data: Dict[str, Any], train_number: str) -> Dict[str, Any]:
        """
        Normalizes external API data to RouteMaster's internal format.
        """
        return {
            "train_number": train_number,
            "train_name": data.get("train_name", "Unknown"),
            "current_station_name": data.get("current_station", "Unknown"),
            "delay_minutes": int(data.get("delay", 0)),
            "status_message": data.get("status_message", "In Transit"),
            "last_updated": data.get("last_updated", datetime.utcnow().isoformat()),
            "source": "RappidAPI Live",
            "raw_data": data
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "live_status_service",
            "api_circuit_breaker_state": self._api_circuit_breaker.state.name,
            "api_circuit_breaker_failures": self._api_circuit_breaker.failure_count,
            "redis_circuit_breaker_state": self._redis_circuit_breaker.state.name,
            "redis_circuit_breaker_failures": self._redis_circuit_breaker.failure_count,
            "status_requests_total": self._metrics.get_counter("status_requests_total"),
            "status_requests_success": self._metrics.get_counter("status_requests_success"),
            "status_requests_failed": self._metrics.get_counter("status_requests_failed"),
            "status_requests_cached": self._metrics.get_counter("status_requests_cached"),
            "status_requests_coalesced": self._metrics.get_counter("status_requests_coalesced"),
            "status_request_duration_p50": self._metrics.get_percentile("status_request_duration_seconds", 50),
            "status_request_duration_p95": self._metrics.get_percentile("status_request_duration_seconds", 95),
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if (self._api_circuit_breaker.state == CircuitState.CLOSED and 
                                   self._redis_circuit_breaker.state == CircuitState.CLOSED) else "degraded",
            "service": "live_status_service",
            "api_circuit_breaker": self._api_circuit_breaker.state.name,
            "redis_circuit_breaker": self._redis_circuit_breaker.state.name,
            "is_enabled": self.enabled,
            "session_active": self._session is not None and not self._session.closed,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self, breaker_name: str = "all"):
        """Reset circuit breaker(s) to closed state."""
        if breaker_name == "all" or breaker_name == "api":
            self._api_circuit_breaker.reset()
        if breaker_name == "all" or breaker_name == "redis":
            self._redis_circuit_breaker.reset()
        logger.info(f"🔄 [LIVE_STATUS] Circuit breaker '{breaker_name}' reset")
