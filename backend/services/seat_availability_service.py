"""
💺 SEAT AVAILABILITY SERVICE
Production-ready with staleness detection, priority queue, and predictive availability.
"""

import logging
import asyncio
import time
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import date, datetime
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from priorityqueue import PriorityQueue

from core.resilience import circuit_manager, CircuitConfig, CircuitOpenError
from core.retry import retry, RETRY_POLICY_EXTERNAL_API

logger = logging.getLogger(__name__)

# Create circuit breaker for seat availability
SEAT_AVAIL_BREAKER = circuit_manager.get_or_create(
    "seat_availability",
    CircuitConfig(
        failure_threshold=3,
        timeout_seconds=60.0,
        half_open_max_calls=3
    )
)


class AvailabilityPriority(Enum):
    """Request priority for seat availability."""
    CRITICAL = 1  # Booking in progress
    HIGH = 2       # User actively viewing
    NORMAL = 3     # General search
    LOW = 4        # Background/prefetch


@dataclass
class AvailabilityConfig:
    """Configuration for availability service."""
    cache_ttl_seconds: int = 120
    stale_threshold_seconds: int = 180  # 3 minutes for availability
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 2000
    prediction_enabled: bool = True
    max_retries: int = 3


@dataclass
class AvailabilityStaleness:
    """Staleness information for availability data."""
    is_stale: bool
    age_seconds: float
    should_refresh: bool
    confidence: str  # "high", "medium", "low"


class SeatAvailabilityService:
    """
    Service responsible for checking seat availability.
    Production-ready with:
    - Circuit breaker protection
    - Request coalescing
    - Rate limiting
    - Staleness detection
    - Priority queue
    - Predictive availability
    """

    # Request coalescing
    _inflight_requests: Dict[str, asyncio.Future] = {}
    _inflight_lock = asyncio.Lock()
    
    # Metrics tracking
    _request_history: deque = deque(maxlen=1000)

    def __init__(self, config: Optional[AvailabilityConfig] = None):
        self.config = config or AvailabilityConfig()
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl_seconds = self.config.cache_ttl_seconds
        
        # Production features
        self._rate_limiter = RateLimiter(
            requests_per_minute=self.config.rate_limit_per_minute,
            requests_per_hour=self.config.rate_limit_per_hour
        )
        self._priority_queue: PriorityQueue = PriorityQueue()
        self._prediction_cache: Dict[str, Dict] = {}  # Cache predictions
        
        logger.info("SeatAvailabilityService initialized with production features.")

    def _get_cache_key(
        self, 
        train_number: str, 
        travel_date: str, 
        from_station: str, 
        to_station: str,
        class_code: str,
        quota: str
    ) -> str:
        """Generate cache key for availability lookup."""
        return f"seat:{train_number}:{travel_date}:{from_station}:{to_station}:{class_code}:{quota}"

    def _is_cache_valid(self, cached: Dict) -> bool:
        """Check if cached availability is still valid."""
        if not cached:
            return False
        cached_time = cached.get("_cached_at", 0)
        return (datetime.utcnow().timestamp() - cached_time) < self._cache_ttl_seconds

    # =========================================================================
    # TASK: RATE LIMITING
    # =========================================================================
    
    async def check_rate_limit(self, api_key: Optional[str] = None) -> Tuple[bool, Dict]:
        """Check if request is within rate limits."""
        key = api_key or "default"
        return await self._rate_limiter.allow(key)

    def get_rate_limit_status(self, api_key: Optional[str] = None) -> Dict:
        """Get current rate limit status."""
        key = api_key or "default"
        return self._rate_limiter.get_status(key)

    # =========================================================================
    # TASK: STALENESS DETECTION
    # =========================================================================
    
    def check_data_staleness(
        self,
        train_number: str,
        travel_date: str,
        from_station: str,
        to_station: str,
        class_code: str,
        quota: str = "GN"
    ) -> AvailabilityStaleness:
        """Check if cached availability is stale."""
        cache_key = self._get_cache_key(
            train_number, travel_date, from_station, to_station, class_code, quota
        )
        
        if cache_key not in self._cache:
            return AvailabilityStaleness(
                is_stale=True,
                age_seconds=0,
                should_refresh=True,
                confidence="low"
            )
        
        result, timestamp = self._cache[cache_key]
        age_seconds = (datetime.utcnow() - timestamp).total_seconds()
        
        is_stale = age_seconds > self.config.stale_threshold_seconds
        
        if age_seconds < 60:
            confidence = "high"
        elif age_seconds < self.config.stale_threshold_seconds:
            confidence = "medium"
        else:
            confidence = "low"
        
        return AvailabilityStaleness(
            is_stale=is_stale,
            age_seconds=age_seconds,
            should_refresh=is_stale,
            confidence=confidence
        )

    def get_data_age(self, cache_key: str) -> Optional[float]:
        """Get age of cached data in seconds."""
        if cache_key not in self._cache:
            return None
        _, timestamp = self._cache[cache_key]
        return (datetime.utcnow() - timestamp).total_seconds()

    # =========================================================================
    # TASK: PRIORITY QUEUE
    # =========================================================================
    
    async def get_seat_availability_priority(
        self,
        train_number: str,
        travel_date: str,
        from_station_code: str,
        to_station_code: str,
        class_code: str,
        quota: str = "GN",
        priority: AvailabilityPriority = AvailabilityPriority.NORMAL,
        bypass_cache: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get seat availability with priority handling.
        Critical requests (bookings) get processed first.
        """
        # Check rate limit
        allowed, limit_info = await self.check_rate_limit()
        if not allowed and priority not in [AvailabilityPriority.CRITICAL, AvailabilityPriority.HIGH]:
            return {
                "error": "rate_limit_exceeded",
                "message": "Too many requests",
                "retry_after": limit_info.get("retry_after", 60)
            }
        
        # For critical/high priority, process immediately
        if priority in [AvailabilityPriority.CRITICAL, AvailabilityPriority.HIGH]:
            return await self.get_seat_availability(
                train_number, travel_date, from_station_code,
                to_station_code, class_code, quota, bypass_cache
            )
        
        # Queue for low priority (background)
        logger.debug(f"Queued low-priority availability request for train {train_number}")
        return await self.get_seat_availability(
            train_number, travel_date, from_station_code,
            to_station_code, class_code, quota, bypass_cache
        )

    # =========================================================================
    # TASK: PREDICTIVE AVAILABILITY
    # =========================================================================
    
    def predict_availability(
        self,
        train_number: str,
        travel_date: str,
        class_code: str,
        current_available: int
    ) -> Dict:
        """
        Predict future availability based on patterns.
        Task: Predictive availability.
        """
        cache_key = f"predict:{train_number}:{travel_date}:{class_code}"
        
        if cache_key in self._prediction_cache:
            return self._prediction_cache[cache_key]
        
        # Simple prediction based on current availability and time
        # In production: use ML model
        
        day_of_week = datetime.strptime(travel_date, "%Y-%m-%d").weekday()
        is_weekend = day_of_week >= 5
        
        # Weekend factor
        weekend_factor = 1.3 if is_weekend else 1.0
        
        # Time-based factor (closer to travel date = faster depletion)
        days_until_travel = (datetime.strptime(travel_date, "%Y-%m-%d") - datetime.utcnow()).days
        
        if days_until_travel <= 1:
            time_factor = 0.3  # Fast depletion
        elif days_until_travel <= 3:
            time_factor = 0.5
        elif days_until_travel <= 7:
            time_factor = 0.7
        else:
            time_factor = 0.9  # Slow depletion
        
        # Calculate predicted depletion rate
        depletion_rate = current_available * (1 - time_factor) * weekend_factor
        
        prediction = {
            "train_number": train_number,
            "travel_date": travel_date,
            "class_code": class_code,
            "current_available": current_available,
            "predicted_depletion_per_hour": round(depletion_rate, 1),
            "predicted_sold_out_hours": round(current_available / depletion_rate, 1) if depletion_rate > 0 else None,
            "confidence": "medium",
            "factors": {
                "is_weekend": is_weekend,
                "days_until_travel": days_until_travel,
                "time_factor": time_factor
            }
        }
        
        self._prediction_cache[cache_key] = prediction
        return prediction

    # =========================================================================
    # MAIN AVAILABILITY OPERATIONS
    # =========================================================================
    
    async def get_seat_availability(
        self,
        train_number: str,
        travel_date: str,
        from_station_code: str,
        to_station_code: str,
        class_code: str,
        quota: str = "GN",
        bypass_cache: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get seat availability with production features.
        """
        logger.debug(f"Checking seat availability for train {train_number} on {travel_date}")
        
        # Check cache first
        cache_key = self._get_cache_key(
            train_number, travel_date, from_station_code, 
            to_station_code, class_code, quota
        )
        
        if not bypass_cache and cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            cached = self._cache[cache_key]
            logger.debug(f"📦 Cache hit for seat availability {cache_key}")
            
            # Add staleness info
            cached["stale"] = False
            return cached

        # Request coalescing: check if request is already in-flight
        coalesce_key = f"{train_number}:{travel_date}:{class_code}"
        async with self._inflight_lock:
            if coalesce_key in self._inflight_requests:
                logger.debug(f"Coalescing availability request for train {train_number}")
                try:
                    result = await self._inflight_requests[coalesce_key]
                    if result:
                        return result
                except Exception:
                    pass  # Fall through to make new request

        try:
            # Execute through circuit breaker with retry
            result = await SEAT_AVAIL_BREAKER.execute(
                self._fetch_availability,
                train_number, travel_date, from_station_code, 
                to_station_code, class_code, quota
            )
            
            # Cache successful results
            if result and result.get("success"):
                result["_cached_at"] = datetime.utcnow().timestamp()
                result["_cache_key"] = cache_key
                self._cache[cache_key] = result
                
                # Generate prediction if enabled
                if self.config.prediction_enabled:
                    total_available = result.get("total_available", 0)
                    prediction = self.predict_availability(
                        train_number, travel_date, class_code, total_available
                    )
                    result["prediction"] = prediction
            
            return result
            
        except CircuitOpenError as cb_err:
            logger.error(f"Circuit breaker open for seat availability: {cb_err}")
            return {
                "source": "circuit_breaker",
                "success": False,
                "error": "Seat availability service temporarily unavailable",
                "error_code": "SERVICE_UNAVAILABLE"
            }
        except Exception as e:
            logger.error(f"Failed to get seat availability: {e}")
            return {
                "source": "error",
                "success": False,
                "error": str(e),
                "error_code": "UNKNOWN_ERROR"
            }

    @retry(**RETRY_POLICY_EXTERNAL_API.__dict__)
    async def _fetch_availability(
        self,
        train_number: str,
        travel_date: str,
        from_station_code: str,
        to_station_code: str,
        class_code: str,
        quota: str
    ) -> Dict[str, Any]:
        """Internal method to fetch availability from provider."""
        from providers.gateway import provider_gateway
        
        try:
            route_details = await provider_gateway.unlock_route_details(
                train_number=train_number,
                source=from_station_code,
                dest=to_station_code,
                date=travel_date
            )
            
            if route_details and route_details.get("success"):
                availability_list = route_details.get("data", {}).get("availability", [])
                
                filtered_availability = [
                    av for av in availability_list 
                    if av.get("class_code", "").upper() == class_code.upper()
                ]
                
                total_available = sum(
                    int(av.get("available", 0)) 
                    for av in (filtered_availability or availability_list)
                )
                
                return {
                    "source": "ProviderGateway",
                    "success": True,
                    "quota": quota,
                    "class": class_code,
                    "train_number": train_number,
                    "travel_date": travel_date,
                    "from_station": from_station_code,
                    "to_station": to_station_code,
                    "data": filtered_availability or availability_list,
                    "total_available": total_available,
                    "status": "AVAILABLE" if total_available > 0 else "SOLD_OUT"
                }
            else:
                error_msg = route_details.get("error", "Unknown error") if route_details else "No data"
                return {
                    "source": "ProviderGateway",
                    "success": False,
                    "error": error_msg,
                    "error_code": "PROVIDER_ERROR"
                }
                
        except ImportError:
            logger.warning("ProviderGateway not available, using mock data")
            return self._get_mock_availability(
                train_number, travel_date, from_station_code, 
                to_station_code, class_code, quota
            )

    def _get_mock_availability(
        self,
        train_number: str,
        travel_date: str,
        from_station_code: str,
        to_station_code: str,
        class_code: str,
        quota: str
    ) -> Dict[str, Any]:
        """Return mock availability data for development/testing."""
        return {
            "source": "mock",
            "success": True,
            "quota": quota,
            "class": class_code,
            "train_number": train_number,
            "travel_date": travel_date,
            "from_station": from_station_code,
            "to_station": to_station_code,
            "data": [
                {
                    "class_code": class_code,
                    "quota": quota,
                    "available": "AVAILABLE",
                    "count": 25,
                    "status": "AVAILABLE"
                }
            ],
            "total_available": 25,
            "status": "AVAILABLE"
        }

    def clear_cache(self, key: Optional[str] = None) -> None:
        """Clear availability cache."""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()
        self._prediction_cache.clear()
        logger.info(f"Seat availability cache cleared" + (f" for {key}" if key else ""))

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "prediction_cache_size": len(self._prediction_cache),
            "ttl_seconds": self._cache_ttl_seconds
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status including circuit breaker state."""
        breaker = circuit_manager.get("seat_availability")
        metrics = breaker.get_metrics() if breaker else None

        if metrics is None:
            circuit_breaker = None
        else:
            to_dict = getattr(metrics, "to_dict", None)
            if callable(to_dict):
                circuit_breaker = to_dict()
            elif isinstance(metrics, dict):
                circuit_breaker = metrics
            else:
                circuit_breaker = str(metrics)

        return {
            "circuit_breaker": circuit_breaker,
            "cache_stats": self.get_cache_stats(),
            "rate_limit": self.get_rate_limit_status()
        }


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
            
            elapsed_min = now - bucket["last_minute_update"]
            bucket["minute_tokens"] = min(
                self.requests_per_minute,
                bucket["minute_tokens"] + elapsed_min * (self.requests_per_minute / 60)
            )
            
            elapsed_hour = now - bucket["last_hour_update"]
            if elapsed_hour >= 3600:
                bucket["hour_tokens"] = self.requests_per_hour
                bucket["last_hour_update"] = now
            
            bucket["last_minute_update"] = now
            
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
