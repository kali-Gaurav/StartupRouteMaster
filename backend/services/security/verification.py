"""
Verification & Unlock Details System - PRODUCTION VERSION
With resilience patterns, circuit breakers, and comprehensive error handling
"""
import asyncio
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple, Type, cast
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from enum import Enum
from dataclasses import dataclass, field
from dataclasses import asdict
import json
import logging
from collections import deque
from contextlib import asynccontextmanager

from database.config import Config
from sqlalchemy.orm import Session
from core.route_engine.data_provider import DataProvider
from core.data_utils.segment import SegmentDetail, JourneyOption
from database.models import Stop
from services.cache_service import cache_service
from services.live_status_service import LiveStatusService, LiveStatusConfig, LiveStatusProvider
from services.seat_verification import SeatVerificationService
from services.fare_service import FareService
from core.resilience.core import circuit_manager, CircuitBreakerState
from core.resilience.retry import RetryPolicy, retry_sync

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    """Status of verification check"""
    VERIFIED = "verified"
    PENDING = "pending"
    FAILED = "failed"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class SeatCheckResult:
    """Result of seat availability check"""
    status: VerificationStatus
    total_seats: int
    available_seats: int
    booked_seats: int
    waiting_list_position: Optional[int] = None
    message: str = ""
    response_time_ms: int = 0
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "total_seats": self.total_seats,
            "available_seats": self.available_seats,
            "booked_seats": self.booked_seats,
            "waiting_list_position": self.waiting_list_position,
            "message": self.message,
            "response_time_ms": self.response_time_ms,
            "source": self.source
        }


@dataclass
class TrainScheduleCheckResult:
    """Result of train schedule verification"""
    status: VerificationStatus
    scheduled_departure: str
    scheduled_arrival: str
    actual_departure: Optional[str] = None
    actual_arrival: Optional[str] = None
    delay_minutes: int = 0
    message: str = ""
    response_time_ms: int = 0
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "scheduled_departure": self.scheduled_departure,
            "scheduled_arrival": self.scheduled_arrival,
            "actual_departure": self.actual_departure,
            "actual_arrival": self.actual_arrival,
            "delay_minutes": self.delay_minutes,
            "message": self.message,
            "response_time_ms": self.response_time_ms,
            "source": self.source
        }


@dataclass
class FareCheckResult:
    """Result of fare verification"""
    status: VerificationStatus
    base_fare: float
    GST: float
    total_fare: float
    applicable_discounts: Optional[List[str]] = None
    cancellation_charges: float = 0.0
    message: str = ""
    response_time_ms: int = 0
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "base_fare": self.base_fare,
            "GST": self.GST,
            "total_fare": self.total_fare,
            "applicable_discounts": self.applicable_discounts,
            "cancellation_charges": self.cancellation_charges,
            "message": self.message,
            "response_time_ms": self.response_time_ms,
            "source": self.source
        }


@dataclass
class VerificationDetails:
    """Complete verification result for a journey"""
    journey_id: str
    verification_timestamp: str
    overall_status: VerificationStatus
    seat_verification: SeatCheckResult
    schedule_verification: TrainScheduleCheckResult
    fare_verification: FareCheckResult
    restrictions: List[str]
    warnings: List[str]
    is_bookable: bool
    response_time_ms: int = 0
    cache_hit: bool = False
    sources: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "journey_id": self.journey_id,
            "verification_timestamp": self.verification_timestamp,
            "overall_status": self.overall_status.value,
            "seat_verification": self.seat_verification.to_dict(),
            "schedule_verification": self.schedule_verification.to_dict(),
            "fare_verification": self.fare_verification.to_dict(),
            "restrictions": self.restrictions,
            "warnings": self.warnings,
            "is_bookable": self.is_bookable,
            "response_time_ms": self.response_time_ms,
            "cache_hit": self.cache_hit,
            "sources": self.sources
        }


@dataclass
class VerificationConfig:
    """Configuration for verification service."""
    cache_ttl_seconds: int = 180
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


class VerificationService:
    """
    Unified Verification Service: Production-ready with resilience patterns.
    """
    
    def __init__(self, config: Optional[VerificationConfig] = None):
        self.config = config or VerificationConfig()
        self.data_provider = DataProvider()
        self.data_provider.detect_available_features()
        
        # Initialize live status service with circuit breaker
        live_config = LiveStatusConfig(
            cache_ttl_seconds=self.config.cache_ttl_seconds,
            retry_policy=self.config.retry_policy,
            timeout_seconds=self.config.timeout_seconds
        )
        self.live_status_service = LiveStatusService(config=live_config)
        
        # Thread pool for blocking operations
        self._executor = ThreadPoolExecutor(
            max_workers=3,
            thread_name_prefix="verification"
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Circuit breakers for each check type
        self._seat_breaker = circuit_manager.get_breaker("seat_verification")
        self._schedule_breaker = circuit_manager.get_breaker("schedule_verification")
        self._fare_breaker = circuit_manager.get_breaker("fare_verification")
        self.verification_service = self
        
        logger.info("VerificationService initialized with resilience patterns")

    def _get_cache_key(self, journey_id: str, travel_date: str) -> str:
        """Generate cache key for verification result."""
        return f"verification:{journey_id}:{travel_date}"

    def _get_cached_result(self, journey_id: str, travel_date: str) -> Optional[VerificationDetails]:
        """Get cached verification result."""
        cache_key = self._get_cache_key(journey_id, travel_date)
        cached = cache_service.get(cache_key)
        if cached:
            result = VerificationDetails(**cached)
            result.cache_hit = True
            return result
        return None

    def _cache_result(self, journey_id: str, travel_date: str, result: VerificationDetails):
        """Cache verification result."""
        cache_key = self._get_cache_key(journey_id, travel_date)
        cache_service.set(cache_key, result.to_dict(), ttl_seconds=self.config.cache_ttl_seconds)

    @retry_sync
    def _verify_seat_availability(
        self,
        trip_id: int,
        travel_date: datetime,
        coach_preference: str,
        train_number: str,
        from_station: str,
        to_station: str
    ) -> SeatCheckResult:
        """Verify seat availability with retry logic."""
        start_time = datetime.utcnow()
        
        try:
            seats_raw = self.data_provider.verify_seat_availability_unified(
                trip_id=trip_id,
                travel_date=travel_date,
                coach_preference=coach_preference,
                train_number=train_number,
                from_station=from_station,
                to_station=to_station
            )
            
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return SeatCheckResult(
                status=VerificationStatus(seats_raw.get("status", "failed")),
                total_seats=seats_raw.get("total_seats", 0),
                available_seats=seats_raw.get("available_seats", 0),
                booked_seats=seats_raw.get("booked_seats", 0),
                message=seats_raw.get("message", ""),
                response_time_ms=response_time_ms,
                source="data_provider"
            )
            
        except Exception as e:
            logger.error(f"Seat verification error: {e}")
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return SeatCheckResult(
                status=VerificationStatus.FAILED,
                total_seats=0,
                available_seats=0,
                booked_seats=0,
                message=str(e),
                response_time_ms=response_time_ms,
                source="error"
            )

    @retry_sync
    def _verify_train_schedule(
        self,
        trip_id: int,
        travel_date: datetime
    ) -> TrainScheduleCheckResult:
        """Verify train schedule with retry logic."""
        start_time = datetime.utcnow()
        
        try:
            sched_raw = self.data_provider.verify_train_schedule_unified(trip_id, travel_date)
            
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return TrainScheduleCheckResult(
                status=VerificationStatus(sched_raw.get("status") or "failed"),
                scheduled_departure="",
                scheduled_arrival="",
                delay_minutes=sched_raw.get("delay_minutes", 0),
                message=sched_raw.get("message", ""),
                response_time_ms=response_time_ms,
                source="data_provider"
            )
            
        except Exception as e:
            logger.error(f"Schedule verification error: {e}")
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return TrainScheduleCheckResult(
                status=VerificationStatus.FAILED,
                scheduled_departure="",
                scheduled_arrival="",
                delay_minutes=0,
                message=str(e),
                response_time_ms=response_time_ms,
                source="error"
            )

    @retry_sync
    def _verify_fare(
        self,
        segment_id: int,
        coach_preference: str,
        train_number: str,
        from_station: str,
        to_station: str
    ) -> FareCheckResult:
        """Verify fare with retry logic."""
        start_time = datetime.utcnow()
        
        try:
            fare_raw = self.data_provider.verify_fare_unified(
                segment_id=segment_id,
                coach_preference=coach_preference,
                train_number=train_number,
                from_station=from_station,
                to_station=to_station
            )
            
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return FareCheckResult(
                status=VerificationStatus(fare_raw.get("status") or "failed"),
                base_fare=fare_raw.get("base_fare", 0.0),
                GST=fare_raw.get("GST", 0.0),
                total_fare=fare_raw.get("total_fare", 0.0),
                message=fare_raw.get("message", ""),
                response_time_ms=response_time_ms,
                source="data_provider"
            )
            
        except Exception as e:
            logger.error(f"Fare verification error: {e}")
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return FareCheckResult(
                status=VerificationStatus.FAILED,
                base_fare=0.0,
                GST=0.0,
                total_fare=0.0,
                message=str(e),
                response_time_ms=response_time_ms,
                source="error"
            )

    async def verify_journey(
        self,
        journey: JourneyOption,
        travel_date: date,
        coach_preference: str = "AC_THREE_TIER",
        passenger_age: int = 30,
        concession_type: Optional[str] = None,
        bypass_cache: bool = False
    ) -> VerificationDetails:
        """
        Verify a journey with all checks running concurrently.
        
        Args:
            journey: The journey option to verify
            travel_date: Date of travel
            coach_preference: Coach class preference
            passenger_age: Passenger age for concessions
            concession_type: Type of concession if applicable
            bypass_cache: Skip cache and fetch fresh data
            
        Returns:
            VerificationDetails with all check results
        """
        start_time = datetime.utcnow()
        travel_date_str = travel_date.isoformat()
        
        # Check cache first
        if not bypass_cache:
            cached = self._get_cached_result(journey.journey_id, travel_date_str)
            if cached:
                logger.debug(f"Cache hit for journey {journey.journey_id}")
                return cached
        
        primary_segment = journey.segments[0] if journey.segments else None
        if not primary_segment:
            raise ValueError("No segments to verify")
        
        # Convert segment info to IDs
        train_num = primary_segment.train_number
        try:
            trip_id = int(train_num)
        except (ValueError, TypeError):
            trip_id = 0
        
        seg_id = primary_segment.segment_id
        dt_travel = datetime.combine(travel_date, datetime.min.time())
        
        # Run all verifications concurrently with semaphore limit
        semaphore = asyncio.Semaphore(self.config.max_concurrent_checks)
        
        async def run_check_with_limit(check_func, *args):
            async with semaphore:
                return check_func(*args)
        
        # Execute checks concurrently
        seat_check, schedule_check, fare_check = await asyncio.gather(
            run_check_with_limit(
                self._verify_seat_availability,
                trip_id, dt_travel, coach_preference,
                train_num, primary_segment.depart_code, primary_segment.arrival_code
            ),
            run_check_with_limit(
                self._verify_train_schedule,
                trip_id, dt_travel
            ),
            run_check_with_limit(
                self._verify_fare,
                seg_id, coach_preference,
                train_num, primary_segment.depart_code, primary_segment.arrival_code
            ),
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(seat_check, Exception):
            seat_check = SeatCheckResult(
                status=VerificationStatus.FAILED,
                total_seats=0, available_seats=0, booked_seats=0,
                message=str(seat_check), source="error"
            )
        if isinstance(schedule_check, Exception):
            schedule_check = TrainScheduleCheckResult(
                status=VerificationStatus.FAILED,
                scheduled_departure="", scheduled_arrival="",
                message=str(schedule_check), source="error"
            )
        if isinstance(fare_check, Exception):
            fare_check = FareCheckResult(
                status=VerificationStatus.FAILED,
                base_fare=0.0, GST=0.0, total_fare=0.0,
                message=str(fare_check), source="error"
            )
        
        # Build restrictions and warnings
        restrictions = []
        warnings = []
        
        if seat_check.status == VerificationStatus.FAILED:
            restrictions.append(f"Seat Verification Failed: {seat_check.message}")
        if fare_check.status == VerificationStatus.FAILED:
            restrictions.append(f"Fare Verification Failed: {fare_check.message}")
        if schedule_check.status == VerificationStatus.FAILED:
            restrictions.append(f"Schedule Verification Failed: {schedule_check.message}")
        
        is_bookable = (
            seat_check.status in [VerificationStatus.VERIFIED, VerificationStatus.PENDING] and
            fare_check.status in [VerificationStatus.VERIFIED, VerificationStatus.PENDING] and
            schedule_check.status in [VerificationStatus.VERIFIED, VerificationStatus.PENDING]
        )
        
        if seat_check.available_seats == 0:
            warnings.append("No seats available - Book for Waiting List")
        
        days_until_travel = (travel_date - date.today()).days
        if days_until_travel > 60:
            restrictions.append("Booking window exceeds 60 days")
            is_bookable = False
        
        response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        result = VerificationDetails(
            journey_id=journey.journey_id,
            verification_timestamp=datetime.now().isoformat(),
            overall_status=VerificationStatus.VERIFIED if is_bookable else VerificationStatus.FAILED,
            seat_verification=seat_check,
            schedule_verification=schedule_check,
            fare_verification=fare_check,
            restrictions=restrictions,
            warnings=warnings,
            is_bookable=is_bookable,
            response_time_ms=response_time_ms,
            sources={
                "seat": seat_check.source,
                "schedule": schedule_check.source,
                "fare": fare_check.source
            }
        )
        
        # Cache the result
        self._cache_result(journey.journey_id, travel_date_str, result)
        
        # Record metrics
        await self._record_metrics(result)
        
        return result

    async def _record_metrics(self, result: VerificationDetails):
        """Record verification metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "journey_id": result.journey_id,
                "status": result.overall_status.value,
                "is_bookable": result.is_bookable,
                "response_time_ms": result.response_time_ms,
                "cache_hit": result.cache_hit
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_verifications": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["is_bookable"])
        response_times = [m["response_time_ms"] for m in self._metrics]
        
        return {
            "total_verifications": total,
            "successful_verifications": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_response_time_ms": sum(response_times) / len(response_times) if response_times else 0,
            "cache_hit_rate": sum(1 for m in self._metrics if m["cache_hit"]) / total if total > 0 else 0.0,
            "circuit_breaker_states": {
                "seat": self._seat_breaker.get_state().value,
                "schedule": self._schedule_breaker.get_state().value,
                "fare": self._fare_breaker.get_state().value
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
                "schedule": self._schedule_breaker.get_state().value,
                "fare": self._fare_breaker.get_state().value
            },
            "metrics": self.get_metrics()
        }

    def clear_cache(self, journey_id: Optional[str] = None):
        """Clear verification cache."""
        if journey_id:
            pattern = f"verification:{journey_id}:*"
        else:
            pattern = "verification:*"
        
        cache_service.get_pattern(pattern)
        logger.info(f"Verification cache cleared for pattern: {pattern}")


# Global instance for production
verification_service = VerificationService()


class RouteVerificationEngine:
    """Orchestrates live verification for routes and caches the outcomes."""

    CLASS_MAPPING = {
        "AC_THREE_TIER": "3A",
        "AC_TWO_TIER": "2A",
        "AC_FIRST_CLASS": "1A",
        "SLEEPER": "SL",
        "AC_TWO": "2A",
        "AC_ONE": "1A"
    }

    def __init__(self, db: Optional[Session] = None, cache: Optional[Any] = None, config: Type[Config] = Config):
        self.db = db
        self.cache = cache or cache_service
        self.live_status_service = LiveStatusService()
        self.seat_service = SeatVerificationService()
        self.fare_service = FareService(config)
        self.ttl = getattr(config, "VERIFICATION_CACHE_TTL", 180)
        self._loop = asyncio.new_event_loop()

    def _cache_key(self, journey_id: str) -> str:
        return f"verification:{journey_id}"

    def _normalize_code(self, code: Optional[str]) -> Optional[str]:
        if not code:
            return None
        return code.strip().upper()

    def _station_code_from_id(self, stop_id: Optional[int]) -> Optional[str]:
        if not stop_id or not self.db:
            return None
        stop = self.db.query(Stop).filter(Stop.id == stop_id).first()
        if not stop or not stop.code:
            return None
        return cast(str, stop.code).upper()

    @staticmethod
    def _map_class(coach_pref: str) -> str:
        key = (coach_pref or "").upper()
        return RouteVerificationEngine.CLASS_MAPPING.get(key, "3A")

    def _build_codes(self, from_code: Optional[str], to_code: Optional[str], from_stop_id: Optional[int], to_stop_id: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
        start_code = self._normalize_code(from_code) or self._station_code_from_id(from_stop_id)
        end_code = self._normalize_code(to_code) or self._station_code_from_id(to_stop_id)
        return start_code, end_code

    def get_cached_verification(self, journey_id: str) -> Optional[Dict]:
        cached = self.cache.get(self._cache_key(journey_id))
        if cached:
            return {**cached, "cached": True}
        return None

    def verify_route(
        self,
        journey_id: str,
        train_number: str,
        travel_date: datetime,
        coach_preference: str = "AC_THREE_TIER",
        quota: str = "GN",
        from_code: Optional[str] = None,
        to_code: Optional[str] = None,
        from_stop_id: Optional[int] = None,
        to_stop_id: Optional[int] = None
    ) -> Dict:
        cache_key = self._cache_key(journey_id)
        cached = self.cache.get(cache_key)
        if cached:
            return {**cached, "cached": True}

        start_code, end_code = self._build_codes(from_code, to_code, from_stop_id, to_stop_id)
        if not start_code or not end_code:
            logging.warning("RouteVerificationEngine: missing station codes for %s", journey_id)

        date_str = travel_date.strftime("%Y-%m-%d") if isinstance(travel_date, datetime) else str(travel_date)
        class_code = self._map_class(coach_preference)

        try:
            live_status = asyncio.run(self.live_status_service.get_live_status(train_number))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            live_status = loop.run_until_complete(self.live_status_service.get_live_status(train_number))
            loop.close()

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                seat_payload = pool.submit(
                    asyncio.run,
                    self.seat_service.check_segment(
                        train_number, start_code or "", end_code or "", date_str, quota, class_code
                    )
                ).result()
        except RuntimeError:
            seat_payload = asyncio.run(self.seat_service.check_segment(
                train_number, start_code or "", end_code or "", date_str, quota, class_code
            ))
        fare_payload = self.fare_service.get_fare(
            train_no=train_number,
            from_station=start_code or "",
            to_station=end_code or "",
            class_code=class_code,
            quota=quota,
            date=date_str
        )

        errors = []
        if live_status and not live_status.get("success"):
            errors.append(live_status.get("message") or live_status.get("error"))
        if seat_payload and not seat_payload.get("success"):
            errors.append(seat_payload.get("error"))
        if fare_payload and not fare_payload.get("success"):
            errors.append(fare_payload.get("error"))

        verified = bool(live_status and live_status.get("success") and seat_payload and seat_payload.get("success") and fare_payload and fare_payload.get("success"))
        status = "verified" if verified else "pending"

        result = {
            "journey_id": journey_id,
            "train_number": train_number,
            "from_station_code": start_code,
            "to_station_code": end_code,
            "class_code": class_code,
            "quota": quota,
            "status": status,
            "verified": verified,
            "live_status": live_status,
            "seat_availability": seat_payload,
            "fare": fare_payload,
            "errors": [e for e in errors if e],
            "timestamp": datetime.utcnow().isoformat(),
            "cached": False,
            "verification_calls": {
                "live": bool(live_status),
                "seat": bool(seat_payload),
                "fare": bool(fare_payload)
            }
        }

        self.cache.set(cache_key, result, ttl_seconds=self.ttl)
        return result

    async def verify_route_async(
        self,
        journey_id: str,
        train_number: str,
        travel_date: datetime,
        coach_preference: str = "AC_THREE_TIER",
        quota: str = "GN",
        from_code: Optional[str] = None,
        to_code: Optional[str] = None,
        from_stop_id: Optional[int] = None,
        to_stop_id: Optional[int] = None
    ) -> Dict:
        return await asyncio.to_thread(
            self.verify_route,
            journey_id,
            train_number,
            travel_date,
            coach_preference,
            quota,
            from_code,
            to_code,
            from_stop_id,
            to_stop_id
        )

    async def verify_routes_batch(
        self,
        candidates: List[Dict],
        travel_date: datetime,
        coach_preference: str = "AC_THREE_TIER",
        quota: str = "GN"
    ) -> List[Dict]:
        if not candidates:
            return []

        loop = asyncio.get_running_loop()
        max_workers = min(len(candidates), 3)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            tasks = [
                loop.run_in_executor(
                    executor,
                    self.verify_route,
                    candidate["journey_id"],
                    candidate["train_no"],
                    travel_date,
                    coach_preference,
                    quota,
                    candidate.get("from_code"),
                    candidate.get("to_code"),
                    candidate.get("from_stop_id"),
                    candidate.get("to_stop_id"),
                )
                for candidate in candidates
            ]
            return await asyncio.gather(*tasks)
class RouteVerificationEngine:
    """
    Orchestrates live verification for routes and caches the outcomes.
    With resilience patterns and concurrent execution.
    """

    CLASS_MAPPING = {
        "AC_THREE_TIER": "3A",
        "AC_TWO_TIER": "2A",
        "AC_FIRST_CLASS": "1A",
        "SLEEPER": "SL",
        "AC_TWO": "2A",
        "AC_ONE": "1A"
    }

    def __init__(
        self, 
        db: Optional[Session] = None, 
        cache: Optional[Any] = None, 
        config: Type[Config] = Config,
        verification_config: Optional[VerificationConfig] = None
    ):
        self.db = db
        self.cache = cache or cache_service
        self.config = config
        self.verification_config = verification_config or VerificationConfig()
        self.verification_service = VerificationService(config=self.verification_config)
        self.ttl = getattr(config, "VERIFICATION_CACHE_TTL", 180)
        self._loop = asyncio.new_event_loop()
        
        # Circuit breaker for route verification
        self._route_breaker = circuit_manager.get_breaker("route_verification")

    def _cache_key(self, journey_id: str) -> str:
        return f"verification:{journey_id}"

    def _normalize_code(self, code: Optional[str]) -> Optional[str]:
        if not code:
            return None
        return code.strip().upper()

    def _station_code_from_id(self, stop_id: Optional[int]) -> Optional[str]:
        if not stop_id or not self.db:
            return None
        stop = self.db.query(Stop).filter(Stop.id == stop_id).first()
        if not stop or not stop.code:
            return None
        return cast(str, stop.code).upper()

    @staticmethod
    def _map_class(coach_pref: str) -> str:
        key = (coach_pref or "").upper()
        return RouteVerificationEngine.CLASS_MAPPING.get(key, "3A")

    def _build_codes(
        self, 
        from_code: Optional[str], 
        to_code: Optional[str], 
        from_stop_id: Optional[int], 
        to_stop_id: Optional[int]
    ) -> Tuple[Optional[str], Optional[str]]:
        start_code = self._normalize_code(from_code) or self._station_code_from_id(from_stop_id)
        end_code = self._normalize_code(to_code) or self._station_code_from_id(to_stop_id)
        return start_code, end_code

    def get_cached_verification(self, journey_id: str) -> Optional[Dict]:
        """Get cached verification result."""
        cached = self.cache.get(self._cache_key(journey_id))
        if cached:
            return {**cached, "cached": True}
        return None

    @circuit_manager.get_breaker("route_verification").decorate
    def verify_route(
        self,
        journey_id: str,
        train_number: str,
        travel_date: datetime,
        coach_preference: str = "AC_THREE_TIER",
        quota: str = "GN",
        from_code: Optional[str] = None,
        to_code: Optional[str] = None,
        from_stop_id: Optional[int] = None,
        to_stop_id: Optional[int] = None,
        bypass_cache: bool = False
    ) -> Dict:
        """
        Verify a route with all checks.
        
        Args:
            journey_id: Unique journey identifier
            train_number: Train number
            travel_date: Date of travel
            coach_preference: Coach class preference
            quota: Booking quota
            from_code: Origin station code
            to_code: Destination station code
            from_stop_id: Origin stop ID (alternative to from_code)
            to_stop_id: Destination stop ID (alternative to to_code)
            bypass_cache: Skip cache and fetch fresh data
            
        Returns:
            Dictionary with verification results
        """
        cache_key = self._cache_key(journey_id)
        
        if not bypass_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return {**cached, "cached": True}

        start_code, end_code = self._build_codes(from_code, to_code, from_stop_id, to_stop_id)
        if not start_code or not end_code:
            logger.warning("RouteVerificationEngine: missing station codes for %s", journey_id)

        date_str = travel_date.strftime("%Y-%m-%d") if isinstance(travel_date, datetime) else str(travel_date)
        class_code = self._map_class(coach_preference)

        # Run live status check
        try:
            live_status = asyncio.run(
                self.verification_service.live_status_service.get_live_status(train_number)
            )
        except RuntimeError:
            loop = asyncio.new_event_loop()
            live_status = loop.run_until_complete(
                self.verification_service.live_status_service.get_live_status(train_number)
            )
            loop.close()

        # Run seat availability check
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                seat_payload = pool.submit(
                    asyncio.run,
                    self.verification_service._verify_seat_availability(
                        0,  # trip_id
                        datetime.combine(travel_date, datetime.min.time()),
                        coach_preference,
                        train_number,
                        start_code or "",
                        end_code or ""
                    )
                ).result()
                if isinstance(seat_payload, SeatCheckResult):
                    seat_payload = seat_payload.to_dict()
        except RuntimeError:
            seat_payload = asyncio.run(
                self.verification_service._verify_seat_availability(
                    0, datetime.combine(travel_date, datetime.min.time()),
                    coach_preference, train_number, start_code or "", end_code or ""
                )
            )
            if isinstance(seat_payload, SeatCheckResult):
                seat_payload = seat_payload.to_dict()

        # Run fare check
        fare_payload = self.verification_service._verify_fare(
            0,  # segment_id
            coach_preference,
            train_number,
            start_code or "",
            end_code or ""
        )
        if isinstance(fare_payload, FareCheckResult):
            fare_payload = fare_payload.to_dict()

        errors = []
        if live_status and not live_status.get("success"):
            errors.append(live_status.get("message") or live_status.get("error"))
        if seat_payload and not seat_payload.get("success"):
            errors.append(seat_payload.get("error"))
        if fare_payload and not fare_payload.get("success"):
            errors.append(fare_payload.get("error"))

        verified = bool(
            live_status and live_status.get("success") and 
            seat_payload and seat_payload.get("success") and 
            fare_payload and fare_payload.get("success")
        )
        status = "verified" if verified else "pending"

        result = {
            "journey_id": journey_id,
            "train_number": train_number,
            "from_station_code": start_code,
            "to_station_code": end_code,
            "class_code": class_code,
            "quota": quota,
            "status": status,
            "verified": verified,
            "live_status": live_status,
            "seat_availability": seat_payload,
            "fare": fare_payload,
            "errors": [e for e in errors if e],
            "timestamp": datetime.utcnow().isoformat(),
            "cached": False,
            "verification_calls": {
                "live": bool(live_status),
                "seat": bool(seat_payload),
                "fare": bool(fare_payload)
            }
        }

        self.cache.set(cache_key, result, ttl_seconds=self.ttl)
        return result

    async def verify_route_async(
        self,
        journey_id: str,
        train_number: str,
        travel_date: datetime,
        coach_preference: str = "AC_THREE_TIER",
        quota: str = "GN",
        from_code: Optional[str] = None,
        to_code: Optional[str] = None,
        from_stop_id: Optional[int] = None,
        to_stop_id: Optional[int] = None,
        bypass_cache: bool = False
    ) -> Dict:
        """Async version of verify_route."""
        return await asyncio.to_thread(
            self.verify_route,
            journey_id,
            train_number,
            travel_date,
            coach_preference,
            quota,
            from_code,
            to_code,
            from_stop_id,
            to_stop_id,
            bypass_cache
        )

    async def verify_routes_batch(
        self,
        candidates: List[Dict],
        travel_date: datetime,
        coach_preference: str = "AC_THREE_TIER",
        quota: str = "GN",
        max_concurrent: int = 10
    ) -> List[Dict]:
        """
        Verify multiple routes concurrently.
        
        Args:
            candidates: List of candidate route dictionaries
            travel_date: Date of travel
            coach_preference: Coach class preference
            quota: Booking quota
            max_concurrent: Maximum concurrent verifications
            
        Returns:
            List of verification results
        """
        if not candidates:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def verify_with_limit(candidate: Dict) -> Dict:
            async with semaphore:
                return await self.verify_route_async(
                    journey_id=candidate["journey_id"],
                    train_number=candidate["train_no"],
                    travel_date=travel_date,
                    coach_preference=coach_preference,
                    quota=quota,
                    from_code=candidate.get("from_code"),
                    to_code=candidate.get("to_code"),
                    from_stop_id=candidate.get("from_stop_id"),
                    to_stop_id=candidate.get("to_stop_id")
                )
        
        results = await asyncio.gather(
            *[verify_with_limit(c) for c in candidates],
            return_exceptions=True
        )
        
        output = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch verification error: {result}")
                output.append({"error": str(result)})
            else:
                output.append(result)
        
        return output

    def health_check(self) -> dict:
        """Check engine health."""
        return {
            "status": "healthy",
            "cache_ttl": self.ttl,
            "circuit_breaker": self._route_breaker.get_state().value,
            "verification_service": self.verification_service.health_check()
        }
