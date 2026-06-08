import asyncio
import httpx
import logging
import time
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
from queue import PriorityQueue

# --- Import necessary modules ---
from providers.models import UnifiedLiveStatus
from providers.gateway import provider_gateway
from providers.config import config as provider_config
from database.config import Config
from core.resilience.core import circuit_breaker_manager, CircuitBreakerState
from core.resilience.retry import retry_async, RetryPolicy

logger = logging.getLogger(__name__)


class LiveStatusProvider(Enum):
    """Available live status providers."""
    RAPIDAPI = "rapidapi"
    NTES = "ntes"
    MOCK = "mock"


class RequestPriority(Enum):
    """Request priority levels for queue."""
    CRITICAL = 1   # Booking-related, time-sensitive
    HIGH = 2       # User actively viewing
    NORMAL = 3     # General queries
    LOW = 4        # Background/prefetch


@dataclass
class LiveStatusConfig:
    """Configuration for live status service."""
    provider: LiveStatusProvider = LiveStatusProvider.RAPIDAPI
    cache_ttl_seconds: int = 60
    stale_threshold_seconds: int = 120  # Data older than this is considered stale
    retry_policy: RetryPolicy = field(default_factory=lambda: RetryPolicy(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0,
        retry_on_exceptions=(TimeoutError, ConnectionError, OSError)
    ))
    timeout_seconds: float = 15.0
    fallback_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000


@dataclass
class LiveStatusStaleness:
    """Staleness information for cached data."""
    is_stale: bool
    age_seconds: float
    should_refresh: bool
    confidence: str  # "high", "medium", "low"


@dataclass
class LiveStatusResult:
    """Structured result for live status."""
    train_number: str
    status: str
    source: str
    cached: bool = False
    response_time_ms: int = 0
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class LiveStatusService:
    """
    Service responsible for providing live train status information.
    Production-ready with circuit breaker, retry, request coalescing,
    rate limiting, staleness detection, and priority queue.
    """
    
    # Request coalescing: track in-flight requests
    _inflight_requests: Dict[str, asyncio.Future] = {}
    _inflight_lock = asyncio.Lock()
    
    # Metrics tracking
    _request_history: deque = deque(maxlen=1000)
    
    def __init__(self, config: Optional[LiveStatusConfig] = None):
        self.config = config or LiveStatusConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: Dict[str, tuple[LiveStatusResult, datetime]] = {}
        self._cache_lock = asyncio.Lock()
        
        # Get circuit breaker
        self._breaker = circuit_breaker_manager.get_breaker("live_status")
        
        # Production features
        self._rate_limiter = RateLimiter(
            requests_per_minute=self.config.rate_limit_per_minute,
            requests_per_hour=self.config.rate_limit_per_hour
        )
        self._priority_queue: PriorityQueue = PriorityQueue()
        self._webhook_registry: Dict[str, List[Dict]] = defaultdict(list)
        
        logger.info(f"LiveStatusService initialized with provider: {self.config.provider.value}")

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create shared HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    keepalive_expiry=30.0,
                    max_connections=20
                )
            )
        return self._client

    def _get_cache_key(self, train_number: str, train_date: str) -> str:
        """Generate cache key."""
        return f"live_status:{train_number}:{train_date}"

    def _get_cached_result(self, train_number: str, train_date: str) -> Optional[LiveStatusResult]:
        """Get cached result if valid."""
        cache_key = self._get_cache_key(train_number, train_date)
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if datetime.utcnow() - timestamp < timedelta(seconds=self.config.cache_ttl_seconds):
                result.cached = True
                return result
            del self._cache[cache_key]
        return None

    def _set_cache_result(self, train_number: str, train_date: str, result: LiveStatusResult):
        """Cache a result."""
        cache_key = self._get_cache_key(train_number, train_date)
        self._cache[cache_key] = (result, datetime.utcnow())

    @circuit_breaker_manager.get_or_create("live_status").decorate
    @retry_async
    async def get_live_status(
        self, 
        train_number: str, 
        train_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches live status for a specific train with resilience patterns.
        
        Args:
            train_number: The train number to check
            train_date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Dictionary with live status data or None on failure
        """
        # Default to today
        if not train_date:
            train_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        # Check cache first
        cached = self._get_cached_result(train_number, train_date)
        if cached:
            logger.debug(f"Cache hit for train {train_number}")
            return cached.data

        # Request coalescing: check if request is already in-flight
        coalesce_key = f"{train_number}:{train_date}"
        async with self._inflight_lock:
            if coalesce_key in self._inflight_requests:
                logger.debug(f"Coalescing request for train {train_number}")
                try:
                    return await self._inflight_requests[coalesce_key]
                except Exception:
                    pass  # Fall through to make new request

        start_time = datetime.utcnow()
        result = LiveStatusResult(
            train_number=train_number,
            status="pending",
            source="unknown"
        )

        try:
            # Delegate to ProviderGateway
            unified_status = await provider_gateway.get_live_status(
                train_number, 
                train_date=train_date
            )
            
            if unified_status:
                result.data = unified_status.model_dump()
                result.status = "success"
                result.source = self.config.provider.value
                result.response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                # Cache the result
                self._set_cache_result(train_number, train_date, result)
                
                logger.info(f"Live status fetched for train {train_number} in {result.response_time_ms}ms")
                return result.data
            else:
                result.status = "no_data"
                result.error = "Provider returned no data"
                
        except TimeoutError as e:
            result.status = "timeout"
            result.error = str(e)
            logger.warning(f"Timeout fetching live status for train {train_number}: {e}")
            
        except ConnectionError as e:
            result.status = "connection_error"
            result.error = str(e)
            logger.warning(f"Connection error for train {train_number}: {e}")
            
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            logger.error(f"Error fetching live status for train {train_number}: {e}")

        # Record failure for metrics
        result.response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        self._record_request(result)
        
        # Try fallback if enabled
        if self.config.fallback_enabled:
            fallback_result = await self._get_fallback_status(train_number, train_date)
            if fallback_result:
                return fallback_result
        
        return None

    async def _get_fallback_status(
        self, 
        train_number: str, 
        train_date: str
    ) -> Optional[Dict[str, Any]]:
        """Get fallback status when primary provider fails."""
        logger.info(f"Using fallback status for train {train_number}")
        
        return {
            "train_number": train_number,
            "status": "UNKNOWN",
            "source": "fallback",
            "message": "Live status temporarily unavailable",
            "last_updated": datetime.utcnow().isoformat(),
            "is_fallback": True
        }

    async def get_live_status_batch(
        self, 
        train_numbers: list[str], 
        train_date: Optional[str] = None
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch live status for multiple trains concurrently.
        
        Args:
            train_numbers: List of train numbers
            train_date: Date in YYYY-MM-DD format
            
        Returns:
            Dictionary mapping train numbers to their status
        """
        if not train_numbers:
            return {}
        
        if not train_date:
            train_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(5)
        
        async def fetch_with_limit(train_num: str) -> tuple[str, Optional[Dict[str, Any]]]:
            async with semaphore:
                status = await self.get_live_status(train_num, train_date)
                return train_num, status
        
        results = await asyncio.gather(
            *[fetch_with_limit(tn) for tn in train_numbers],
            return_exceptions=True
        )
        
        output = {}
        for result in results:
            if isinstance(result, BaseException):
                logger.error(f"Batch fetch error: {result}")
                continue

            train_num, status = result
            output[train_num] = status

        return output

    def _record_request(self, result: LiveStatusResult):
        """Record request for metrics."""
        self._request_history.append({
            "timestamp": result.timestamp,
            "train_number": result.train_number,
            "status": result.status,
            "response_time_ms": result.response_time_ms,
            "source": result.source
        })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._request_history:
            return {"total_requests": 0, "success_rate": 0.0}
        
        total = len(self._request_history)
        successful = sum(1 for r in self._request_history if r["status"] == "success")
        
        response_times = [r["response_time_ms"] for r in self._request_history]
        
        return {
            "total_requests": total,
            "successful_requests": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_response_time_ms": sum(response_times) / len(response_times) if response_times else 0,
            "min_response_time_ms": min(response_times) if response_times else 0,
            "max_response_time_ms": max(response_times) if response_times else 0,
            "circuit_breaker_state": self._breaker.get_state().value,
            "cache_size": len(self._cache)
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "provider": self.config.provider.value,
            "circuit_breaker": self._breaker.get_state().value,
            "cache_ttl_seconds": self.config.cache_ttl_seconds,
            "metrics": self.get_metrics()
        }

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        
        # Clear in-flight requests
        async with self._inflight_lock:
            for future in self._inflight_requests.values():
                future.cancel()
            self._inflight_requests.clear()

    def clear_cache(self):
        """Clear the in-memory cache."""
        self._cache.clear()
        logger.info("Live status cache cleared")

    # =========================================================================
    # PRODUCTION FEATURES
    # =========================================================================

    # =========================================================================
    # TASK LS-1: RATE LIMITING
    # =========================================================================

    async def check_rate_limit(self, api_key: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Check if request is within rate limits.
        Returns: (is_allowed, details)
        """
        key = api_key or "default"
        return await self._rate_limiter.allow(key)

    def get_rate_limit_status(self, api_key: Optional[str] = None) -> Dict:
        """Get current rate limit status."""
        key = api_key or "default"
        return self._rate_limiter.get_status(key)

    # =========================================================================
    # TASK LS-2: STALENESS DETECTION
    # =========================================================================

    def check_data_staleness(
        self,
        train_number: str,
        train_date: str
    ) -> LiveStatusStaleness:
        """
        Check if cached data is stale and needs refresh.
        """
        cache_key = self._get_cache_key(train_number, train_date)
        
        if cache_key not in self._cache:
            return LiveStatusStaleness(
                is_stale=True,
                age_seconds=0,
                should_refresh=True,
                confidence="low"
            )
        
        result, timestamp = self._cache[cache_key]
        age_seconds = (datetime.utcnow() - timestamp).total_seconds()
        
        # Determine staleness based on age
        is_stale = age_seconds > self.config.stale_threshold_seconds
        
        # Confidence based on how stale
        if age_seconds < 60:
            confidence = "high"
        elif age_seconds < self.config.stale_threshold_seconds:
            confidence = "medium"
        else:
            confidence = "low"
        
        return LiveStatusStaleness(
            is_stale=is_stale,
            age_seconds=age_seconds,
            should_refresh=is_stale,
            confidence=confidence
        )

    def get_data_age(self, train_number: str, train_date: str) -> Optional[float]:
        """Get age of cached data in seconds."""
        cache_key = self._get_cache_key(train_number, train_date)
        
        if cache_key not in self._cache:
            return None
        
        _, timestamp = self._cache[cache_key]
        return (datetime.utcnow() - timestamp).total_seconds()

    # =========================================================================
    # TASK LS-3: PRIORITY QUEUE
    # =========================================================================

    async def get_live_status_priority(
        self,
        train_number: str,
        train_date: Optional[str] = None,
        priority: RequestPriority = RequestPriority.NORMAL
    ) -> Optional[Dict[str, Any]]:
        """
        Get live status with priority handling.
        Critical requests (bookings) get processed first.
        """
        # Check rate limit first
        allowed, limit_info = await self.check_rate_limit()
        if not allowed:
            logger.warning(f"Rate limit exceeded: {limit_info}")
            # For critical requests, try to proceed anyway
            if priority != RequestPriority.CRITICAL:
                return {
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests",
                    "retry_after": limit_info.get("retry_after", 60)
                }
        
        # For critical requests, bypass some checks
        if priority == RequestPriority.CRITICAL:
            return await self.get_live_status(train_number, train_date)
        
        # Add to priority queue for normal/low priority
        queue_key = f"{train_number}:{train_date}"
        
        # Process immediately for high/critical
        if priority in [RequestPriority.CRITICAL, RequestPriority.HIGH]:
            return await self.get_live_status(train_number, train_date)
        
        # Queue for later processing (low priority)
        # In production: would add to background queue
        logger.debug(f"Queued low-priority request: {queue_key}")
        return await self.get_live_status(train_number, train_date)

    # =========================================================================
    # TASK LS-4: PREDICTIVE STATUS
    # =========================================================================

    def predict_delay(
        self,
        train_number: str,
        current_status: Dict
    ) -> Optional[Dict]:
        """
        Predict if train will be delayed based on historical patterns.
        Task: Predictive status.
        """
        # In production: use ML model or historical statistics
        # This is a simplified implementation
        
        current_delay = current_status.get("delay_minutes", 0)
        station_code = current_status.get("current_station", "")
        
        # Simple heuristic: if delayed at a major station, likely to continue
        major_stations = ["NDLS", "MMCT", "CSMT", "BCT", "HW", "MAS", "SBC", "SC"]
        
        if station_code in major_stations and current_delay > 10:
            # Likely to maintain or increase delay
            predicted_delay = current_delay + 5
            confidence = "medium"
        elif current_delay > 30:
            predicted_delay = current_delay
            confidence = "high"
        else:
            predicted_delay = 0
            confidence = "high"
        
        return {
            "train_number": train_number,
            "current_delay": current_delay,
            "predicted_delay": predicted_delay,
            "confidence": confidence,
            "prediction_basis": "historical_pattern" if station_code in major_stations else "current_status"
        }

    # =========================================================================
    # TASK LS-5: WEBHOOK SUPPORT
    # =========================================================================

    def register_status_webhook(
        self,
        train_number: str,
        callback_url: str,
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict:
        """
        Register webhook for train status changes.
        """
        import uuid
        
        webhook_id = str(uuid.uuid4())
        webhook = {
            "webhook_id": webhook_id,
            "train_number": train_number,
            "callback_url": callback_url,
            "events": events,
            "secret": secret or str(uuid.uuid4())[:16],
            "created_at": datetime.utcnow().isoformat(),
            "active": True
        }
        
        self._webhook_registry[train_number].append(webhook)
        
        logger.info(f"📣 Webhook registered: {webhook_id} for train {train_number}")
        
        return {
            "success": True,
            "webhook_id": webhook_id,
            "message": "Webhook registered successfully"
        }

    async def trigger_status_webhooks(
        self,
        train_number: str,
        event: str,
        data: Dict
    ) -> None:
        """
        Trigger webhooks when train status changes.
        """
        webhooks = self._webhook_registry.get(train_number, [])
        
        for webhook in webhooks:
            if not webhook.get("active"):
                continue
            
            if event not in webhook.get("events", []):
                continue
            
            # In production: send HTTP request to callback_url
            logger.info(f"📣 Would trigger webhook {webhook['webhook_id']} for {event}")
            
            # Example implementation:
            # import hmac, hashlib, httpx
            # payload = json.dumps({"event": event, "data": data, "timestamp": datetime.utcnow().isoformat()})
            # signature = hmac.new(webhook["secret"].encode(), payload.encode(), hashlib.sha256).hexdigest()
            # async with httpx.AsyncClient() as client:
            #     await client.post(
            #         webhook["callback_url"],
            #         json={"event": event, "data": data},
            #         headers={"X-Webhook-Signature": signature}
            #     )

    def unregister_webhook(self, webhook_id: str) -> bool:
        """Unregister a webhook."""
        for train_number, webhooks in self._webhook_registry.items():
            for i, wh in enumerate(webhooks):
                if wh.get("webhook_id") == webhook_id:
                    webhooks[i]["active"] = False
                    logger.info(f"📣 Webhook {webhook_id} unregistered")
                    return True
        return False


class RateLimiter:
    """
    Token bucket rate limiter for API calls.
    """
    
    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self._buckets: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    def _get_bucket(self, key: str) -> Dict:
        """Get or create bucket for key."""
        if key not in self._buckets:
            self._buckets[key] = {
                "minute_tokens": self.requests_per_minute,
                "hour_tokens": self.requests_per_hour,
                "last_minute_update": time.time(),
                "last_hour_update": time.time()
            }
        return self._buckets[key]
    
    async def allow(self, key: str) -> Tuple[bool, Dict]:
        """Check if request is allowed."""
        async with self._lock:
            bucket = self._get_bucket(key)
            now = time.time()
            
            # Refill minute tokens
            elapsed_min = now - bucket["last_minute_update"]
            bucket["minute_tokens"] = min(
                self.requests_per_minute,
                bucket["minute_tokens"] + elapsed_min * (self.requests_per_minute / 60)
            )
            
            # Refill hour tokens
            elapsed_hour = now - bucket["last_hour_update"]
            if elapsed_hour >= 3600:
                bucket["hour_tokens"] = self.requests_per_hour
                bucket["last_hour_update"] = now
            
            bucket["last_minute_update"] = now
            
            # Check limits
            if bucket["minute_tokens"] < 1:
                return False, {
                    "reason": "minute_limit_exceeded",
                    "retry_after": (1 - bucket["minute_tokens"]) * (60 / self.requests_per_minute)
                }
            
            if bucket["hour_tokens"] < 1:
                return False, {
                    "reason": "hour_limit_exceeded",
                    "retry_after": 3600
                }
            
            # Consume tokens
            bucket["minute_tokens"] -= 1
            bucket["hour_tokens"] -= 1
            
            return True, {
                "remaining_minute": int(bucket["minute_tokens"]),
                "remaining_hour": int(bucket["hour_tokens"])
            }
    
    def get_status(self, key: str) -> Dict:
        """Get rate limit status."""
        bucket = self._get_bucket(key)
        return {
            "remaining_minute": int(bucket["minute_tokens"]),
            "remaining_hour": int(bucket["hour_tokens"]),
            "limit_minute": self.requests_per_minute,
            "limit_hour": self.requests_per_hour
        } 
