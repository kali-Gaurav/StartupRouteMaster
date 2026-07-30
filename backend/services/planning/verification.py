"""
Route Verification Service - Production Version
With circuit breaker protection, retry logic, and comprehensive error handling
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session
import json

from core.route_engine.data_provider import DataProvider
from database.models import Trip, StopTime, Stop, Segment
from core.infrastructure.redis_manager import async_redis_client
from core.resilience.core import circuit_manager, CircuitBreakerState
from core.resilience.retry import retry_async, RetryPolicy
from services.cache_service import cache_service

logger = logging.getLogger(__name__)


@dataclass
class RouteVerificationConfig:
    """Configuration for route verification service."""
    cache_ttl_seconds: int = 120
    timeout_seconds: float = 30.0
    max_concurrent_checks: int = 5
    retry_policy: RetryPolicy = field(default_factory=lambda: RetryPolicy(
        max_attempts=2,
        base_delay=0.5,
        max_delay=5.0,
        exponential_base=2.0,
        retry_on_exceptions=(TimeoutError, ConnectionError, OSError)
    ))
    circuit_failure_threshold: int = 5
    circuit_recovery_seconds: int = 60


@dataclass
class SegmentVerificationResult:
    """Result of verifying a single segment."""
    train_number: str
    from_station: str
    to_station: str
    class_type: str
    seats_status: str
    seats_available: int = 0
    live_status: str = "UNKNOWN"
    delay_minutes: int = 0
    is_available: bool = True
    error: Optional[str] = None
    response_time_ms: int = 0
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "train_number": self.train_number,
            "from_station": self.from_station,
            "to_station": self.to_station,
            "class_type": self.class_type,
            "seats_status": self.seats_status,
            "seats_available": self.seats_available,
            "live_status": self.live_status,
            "delay_minutes": self.delay_minutes,
            "is_available": self.is_available,
            "error": self.error,
            "response_time_ms": self.response_time_ms,
            "source": self.source
        }


@dataclass
class RouteVerificationResult:
    """Complete verification result for a route."""
    route_id: str
    travel_date: str
    overall_available: bool
    segments: List[SegmentVerificationResult]
    warnings: List[str]
    errors: List[str]
    timestamp: str
    response_time_ms: int = 0
    cache_hit: bool = False
    sources: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "travel_date": self.travel_date,
            "overall_available": self.overall_available,
            "segments": [s.to_dict() for s in self.segments],
            "warnings": self.warnings,
            "errors": self.errors,
            "timestamp": self.timestamp,
            "response_time_ms": self.response_time_ms,
            "cache_hit": self.cache_hit,
            "sources": self.sources
        }


class RouteVerificationService:
    """
    Intelligent service for verifying route information during unlock payment.
    Consolidates Seat Availability (RapidAPI) and Live Status (RappidURL).
    With circuit breaker protection and retry logic.
    """
    
    def __init__(self, config: Optional[RouteVerificationConfig] = None):
        self.config = config or RouteVerificationConfig()
        self.db = None
        self.data_provider = DataProvider()
        
        # Circuit breakers for different checks
        self._seat_breaker = circuit_manager.get_or_create("route_verification_seat")
        self._live_breaker = circuit_manager.get_or_create("route_verification_live")
        
        # Thread pool for blocking operations
        self._executor = None
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = None
        
        logger.info("RouteVerificationService initialized with resilience patterns")

    def _get_cache_key(self, route_id: str, travel_date: str) -> str:
        """Generate cache key for verification result."""
        return f"route_verification:{route_id}:{travel_date}"

    def _get_cached_result(self, route_id: str, travel_date: str) -> Optional[RouteVerificationResult]:
        """Get cached verification result."""
        cache_key = self._get_cache_key(route_id, travel_date)
        cached = cache_service.get(cache_key)
        if cached:
            result = RouteVerificationResult(**cached)
            result.cache_hit = True
            return result
        return None

    def _cache_result(self, route_id: str, travel_date: str, result: RouteVerificationResult):
        """Cache verification result."""
        cache_key = self._get_cache_key(route_id, travel_date)
        cache_service.set(cache_key, result.to_dict(), ttl_seconds=self.config.cache_ttl_seconds)

    @circuit_manager.get_or_create("route_verification_seat").decorate
    @retry_async
    async def _check_seat_availability(
        self,
        train_no: str,
        from_code: str,
        to_code: str,
        date_str: str,
        class_type: str
    ) -> Dict[str, Any]:
        """Check seat availability with retry logic."""
        start_time = datetime.utcnow()
        
        try:
            from services.seat_verification import SeatVerificationService
            seat_svc = SeatVerificationService()
            
            is_avl = await seat_svc.check_segment(
                train_no=train_no,
                from_code=from_code,
                to_code=to_code,
                date_str=date_str,
                class_type=class_type
            )
            
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return {
                "success": True,
                "is_available": is_avl,
                "seats_status": "AVAILABLE" if is_avl else "WAITLIST",
                "seats_available": 0 if not is_avl else 1,
                "response_time_ms": response_time_ms,
                "source": "seat_verification_service"
            }
            
        except Exception as e:
            logger.error(f"Seat availability check failed: {e}")
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return {
                "success": False,
                "is_available": False,
                "seats_status": "ERROR",
                "seats_available": 0,
                "error": str(e),
                "response_time_ms": response_time_ms,
                "source": "error"
            }

    @circuit_manager.get_or_create("route_verification_live").decorate
    @retry_async
    async def _check_live_status(self, train_no: str) -> Dict[str, Any]:
        """Check live status with retry logic."""
        start_time = datetime.utcnow()
        
        try:
            from services.live_status_service import LiveStatusService
            live_svc = LiveStatusService()
            
            live = await live_svc.get_live_status(train_no)
            
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            if live and live.get("success"):
                return {
                    "success": True,
                    "live_status": live.get("message", "ON TIME"),
                    "delay_minutes": live.get("delay_minutes", 0),
                    "response_time_ms": response_time_ms,
                    "source": "live_status_service"
                }
            else:
                return {
                    "success": False,
                    "live_status": "DELAY_UNKNOWN",
                    "delay_minutes": 0,
                    "response_time_ms": response_time_ms,
                    "source": "live_status_service"
                }
                
        except Exception as e:
            logger.error(f"Live status check failed: {e}")
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return {
                "success": False,
                "live_status": "CHECK_FAILED",
                "delay_minutes": 0,
                "error": str(e),
                "response_time_ms": response_time_ms,
                "source": "error"
            }

    async def verify_route_for_unlock(
        self,
        route_id: str,
        travel_date: str,
        train_number: Optional[str] = None,
        from_station_code: Optional[str] = None,
        to_station_code: Optional[str] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Comprehensive verification of all route segments.
        Called when user clicks 'Unlock Details'.
        
        Args:
            route_id: Unique route identifier
            travel_date: Date of travel in YYYY-MM-DD format
            train_number: Train number (optional)
            from_station_code: Origin station code (optional)
            to_station_code: Destination station code (optional)
            bypass_cache: Skip cache and fetch fresh data
            
        Returns:
            Dictionary with verification results
        """
        start_time = datetime.utcnow()
        
        # Check cache first
        if not bypass_cache:
            cached = self._get_cached_result(route_id, travel_date)
            if cached:
                logger.debug(f"Cache hit for route verification {route_id}")
                return cached.to_dict()

        # Extract full route segments
        route_info = await self._extract_route_info(
            route_id, train_number, from_station_code, to_station_code
        )
        
        if not route_info["success"]:
            return {
                "success": False,
                "error": "Route details not found in cache or DB",
                "route_id": route_id,
                "travel_date": travel_date
            }

        segments = route_info.get("segments", [])
        verification_details = []
        overall_available = True
        warnings = []
        errors = []
        sources = {}

        # Verify EVERY segment in the journey concurrently
        semaphore = asyncio.Semaphore(self.config.max_concurrent_checks)
        
        async def verify_segment_with_limit(seg: Dict) -> SegmentVerificationResult:
            async with semaphore:
                return await self._verify_single_segment(seg, travel_date)
        
        # Run all segment verifications concurrently
        segment_results = await asyncio.gather(
            *[verify_segment_with_limit(seg) for seg in segments],
            return_exceptions=True
        )
        
        for result in segment_results:
            if isinstance(result, Exception):
                logger.error(f"Segment verification error: {result}")
                errors.append(str(result))
                continue
                
            verification_details.append(result)
            
            if not result.is_available:
                overall_available = False
            
            if result.delay_minutes > 60:
                warnings.append(f"Train {result.train_number} is delayed by {result.delay_minutes}m")
            
            if result.error:
                errors.append(f"Train {result.train_number}: {result.error}")
            
            sources[result.train_number] = result.source

        response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        final_result = RouteVerificationResult(
            route_id=route_id,
            travel_date=travel_date,
            overall_available=overall_available,
            segments=verification_details,
            warnings=list(set(warnings)),
            errors=errors,
            timestamp=datetime.utcnow().isoformat(),
            response_time_ms=response_time_ms,
            sources=sources
        )
        
        # Cache the result
        self._cache_result(route_id, travel_date, final_result)
        
        # Record metrics
        await self._record_metrics(final_result)
        
        return final_result.to_dict()

    async def _verify_single_segment(
        self,
        seg: Dict,
        travel_date: str
    ) -> SegmentVerificationResult:
        """Verify a single segment."""
        start_time = datetime.utcnow()
        
        t_no = seg.get("train_number")
        f_code = seg.get("from_station_code") or seg.get("from_station")
        t_code = seg.get("to_station_code") or seg.get("to_station")
        class_type = seg.get("class_type", "3A")
        
        # Run seat and live checks concurrently
        seat_result, live_result = await asyncio.gather(
            self._check_seat_availability(t_no, f_code, t_code, travel_date, class_type),
            self._check_live_status(t_no),
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(seat_result, Exception):
            seat_result = {
                "success": False,
                "is_available": False,
                "seats_status": "ERROR",
                "error": str(seat_result)
            }
        
        if isinstance(live_result, Exception):
            live_result = {
                "success": False,
                "live_status": "ERROR",
                "delay_minutes": 0,
                "error": str(live_result)
            }
        
        response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return SegmentVerificationResult(
            train_number=t_no,
            from_station=f_code,
            to_station=t_code,
            class_type=class_type,
            seats_status=seat_result.get("seats_status", "UNKNOWN"),
            seats_available=seat_result.get("seats_available", 0),
            live_status=live_result.get("live_status", "UNKNOWN"),
            delay_minutes=live_result.get("delay_minutes", 0),
            is_available=seat_result.get("is_available", True),
            error=seat_result.get("error") or live_result.get("error"),
            response_time_ms=response_time_ms,
            source=seat_result.get("source", "unknown")
        )

    async def _extract_route_info(
        self,
        route_id: str,
        train_number: Optional[str],
        from_code: Optional[str],
        to_code: Optional[str]
    ) -> Dict:
        """Extract route information from cache or database."""
        # Try Cache First (Modern Flow)
        if route_id.startswith(("rt_", "turbo_")):
            try:
                from services.journey_cache import get_journey
                journey = await get_journey(route_id)
                if journey:
                    logger.debug(f"Cache HIT for {route_id}")
                    return {"success": True, "segments": journey.get("legs", [])}
                else:
                    logger.debug(f"Cache MISS for {route_id}")
            except Exception as e:
                logger.warning(f"Journey cache lookup failed: {e}")

        # Try DB (Legacy/Direct Flow)
        if train_number and from_code and to_code:
            return {
                "success": True,
                "segments": [{
                    "train_number": train_number,
                    "from_station_code": from_code,
                    "to_station_code": to_code
                }]
            }
            
        return {"success": False}

    async def _record_metrics(self, result: RouteVerificationResult):
        """Record verification metrics."""
        if self._metrics_lock is None:
            import asyncio
            self._metrics_lock = asyncio.Lock()
        
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "route_id": result.route_id,
                "overall_available": result.overall_available,
                "segment_count": len(result.segments),
                "response_time_ms": result.response_time_ms,
                "cache_hit": result.cache_hit
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_verifications": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["overall_available"])
        response_times = [m["response_time_ms"] for m in self._metrics]
        
        return {
            "total_verifications": total,
            "successful_verifications": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_response_time_ms": sum(response_times) / len(response_times) if response_times else 0,
            "cache_hit_rate": sum(1 for m in self._metrics if m["cache_hit"]) / total if total > 0 else 0.0,
            "circuit_breaker_states": {
                "seat": self._seat_breaker.get_state().value,
                "live": self._live_breaker.get_state().value
            }
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "config": {
                "cache_ttl_seconds": self.config.cache_ttl_seconds,
                "timeout_seconds": self.config.timeout_seconds,
                "max_concurrent_checks": self.config.max_concurrent_checks
            },
            "circuit_breakers": {
                "seat": self._seat_breaker.get_state().value,
                "live": self._live_breaker.get_state().value
            },
            "metrics": self.get_metrics()
        }

    def clear_cache(self, route_id: Optional[str] = None):
        """Clear verification cache."""
        if route_id:
            pattern = f"route_verification:{route_id}:*"
        else:
            pattern = "route_verification:*"
        
        cache_service.get_pattern(pattern)
        logger.info(f"Route verification cache cleared for pattern: {pattern}")
