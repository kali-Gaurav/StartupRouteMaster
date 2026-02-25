"""High-level verification orchestrator for route search results."""
import asyncio
import logging
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import partial
from time import monotonic
from typing import Any, Dict, Iterable, List, Optional

from backend.config import Config
from backend.services.cache_service import cache_service
from backend.services.fare_service import FareService
from backend.services.live_status_service import LiveStatusService
from backend.services.seat_availability_service import SeatAvailabilityService

logger = logging.getLogger(__name__)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


@dataclass
class RouteVerification:
    journey_id: str
    verified: bool
    status: str
    live_status: Optional[Dict[str, Any]]
    seat: Optional[Dict[str, Any]]
    fare: Optional[Dict[str, Any]]
    delay_minutes: Optional[int]
    confidence_score: float
    cached: bool
    timestamp: str
    errors: List[str]
    verification_calls: Dict[str, bool]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "journey_id": self.journey_id,
            "status": self.status,
            "verified": self.verified,
            "live_status": self.live_status,
            "seat_availability": self.seat,
            "fare": self.fare,
            "delay_minutes": self.delay_minutes,
            "confidence_score": self.confidence_score,
            "cached": self.cached,
            "timestamp": self.timestamp,
            "errors": self.errors,
            "verification_calls": self.verification_calls,
        }


class VerificationOrchestrator:
    """Orchestrator responsible for rate-limited, cached verification of top routes."""

    def __init__(
        self,
        db: Optional[Any] = None,
        config: Config = Config,
        cache: Optional[Any] = None,
    ):
        self.db = db
        self.cache = cache or cache_service
        self.config = config
        self.live_status_service = LiveStatusService(config)
        self.seat_service = SeatAvailabilityService(config)
        self.fare_service = FareService(config)
        self.cache_ttl = _clamp(getattr(config, "VERIFICATION_CACHE_TTL", 180), 120, 300)
        self.total_timeout = getattr(config, "VERIFICATION_TOTAL_TIMEOUT", 7)
        self.live_timeout = getattr(config, "VERIFICATION_LIVE_TIMEOUT", 5)
        self.seat_timeout = getattr(config, "VERIFICATION_SEAT_TIMEOUT", 6)
        self.fare_timeout = getattr(config, "VERIFICATION_FARE_TIMEOUT", 6)
        self.max_rate_per_sec = getattr(config, "VERIFICATION_RATE_LIMIT_PER_SEC", 10)
        self._rate_window: deque[float] = deque()
        self._rate_lock = asyncio.Lock()
        self._pending_tasks: set[asyncio.Task] = set()

        # enforce our custom timeout values on the services
        self.live_status_service.timeout = self.live_timeout
        self.seat_service.timeout = self.seat_timeout
        self.fare_service.timeout = self.fare_timeout

    def _cache_key(self, journey_id: str, train_no: str, travel_date: datetime, class_code: str, quota: str) -> str:
        date_str = travel_date.strftime("%Y-%m-%d") if isinstance(travel_date, datetime) else str(travel_date)
        return f"verification:{journey_id}:{train_no}:{date_str}:{class_code}:{quota}"

    def _get_cached(self, cache_key: str) -> Optional[Dict[str, Any]]:
        data = self.cache.get(cache_key)
        if not data:
            return None
        data["cached"] = True
        return data

    async def _acquire_rate_slot(self) -> bool:
        async with self._rate_lock:
            now = monotonic()
            cutoff = now - 1.0
            while self._rate_window and self._rate_window[0] < cutoff:
                self._rate_window.popleft()
            if len(self._rate_window) >= self.max_rate_per_sec:
                return False
            self._rate_window.append(now)
            return True

    def _extract_delay(self, live_status: Optional[Dict[str, Any]]) -> Optional[int]:
        if not live_status:
            return None
        if live_status.get("delay_minutes") is not None:
            return live_status.get("delay_minutes")
        stations = live_status.get("stations") or []
        for station in reversed(stations):
            if station.get("delay_minutes") is not None:
                return station.get("delay_minutes")
        return None

    def _compute_confidence(self, live_status: Optional[Dict[str, Any]], seat: Optional[Dict[str, Any]], fare: Optional[Dict[str, Any]], delay: Optional[int]) -> float:
        score = 0.0
        if seat and seat.get("success"):
            score += 0.4
            availability = seat.get("data", {}).get("availability") if isinstance(seat.get("data"), dict) else seat.get("data")
            if isinstance(availability, str) and "AVAILABLE" in availability.upper():
                score += 0.1
        if live_status and live_status.get("success"):
            score += 0.3
            status = live_status.get("status") or ""
            if delay and delay > 0:
                score -= 0.1
        if fare and fare.get("success"):
            score += 0.2
        return round(max(0.0, min(1.0, score)), 3)

    async def _run_blocking(self, func: Any, *args: Any, timeout: float = 5.0) -> Optional[Any]:
        try:
            return await asyncio.wait_for(asyncio.to_thread(partial(func, *args)), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Verification call timed out: %s", func.__name__)
            return None
        except Exception as exc:
            logger.warning("Verification call failed %s: %s", func.__name__, exc)
            return None

    async def _call_live(self, train_number: str) -> Optional[Dict[str, Any]]:
        return await self._run_blocking(self.live_status_service.get_live_status, train_number, timeout=self.live_timeout)

    async def _call_seat(self, train_no: str, date: str, from_station: str, to_station: str, class_code: str, quota: str) -> Optional[Dict[str, Any]]:
        return await self._run_blocking(
            self.seat_service.get_seat_availability,
            train_no,
            date,
            from_station,
            to_station,
            class_code,
            quota,
            timeout=self.seat_timeout
        )

    async def _call_fare(self, train_no: str, from_station: str, to_station: str, class_code: str, quota: str, date: str) -> Optional[Dict[str, Any]]:
        return await self._run_blocking(
            self.fare_service.get_fare,
            train_no,
            from_station,
            to_station,
            class_code,
            quota,
            date,
            timeout=self.fare_timeout
        )

    def _build_verification_result(
        self,
        journey_id: str,
        verified: bool,
        live: Optional[Dict[str, Any]],
        seat: Optional[Dict[str, Any]],
        fare: Optional[Dict[str, Any]],
        cached: bool,
        errors: List[str],
        verification_calls: Dict[str, bool],
    ) -> RouteVerification:
        delay = self._extract_delay(live)
        status = "verified" if verified else ("verifying" if not any(verification_calls.values()) else "pending")
        confidence = self._compute_confidence(live, seat, fare, delay)
        timestamp = datetime.utcnow().isoformat()
        return RouteVerification(
            journey_id=journey_id,
            verified=verified,
            status=status,
            live_status=live,
            seat=seat,
            fare=fare,
            delay_minutes=delay,
            confidence_score=confidence,
            cached=cached,
            timestamp=timestamp,
            errors=errors,
            verification_calls=verification_calls,
        )

    def _store_cache(
        self,
        cache_key: str,
        verification: RouteVerification,
    ) -> None:
        payload = verification.to_dict()
        payload["cached"] = False
        self.cache.set(cache_key, payload, ttl_seconds=self.cache_ttl)

    def _placeholder_verification(self, journey_id: str, reason: Optional[str] = None) -> RouteVerification:
        payload = RouteVerification(
            journey_id=journey_id,
            verified=False,
            status="verifying",
            live_status=None,
            seat=None,
            fare=None,
            delay_minutes=None,
            confidence_score=0.0,
            cached=False,
            timestamp=datetime.utcnow().isoformat(),
            errors=[reason] if reason else [],
            verification_calls={"live": False, "seat": False, "fare": False},
        )
        return payload

    def _rate_limited_verification(self, journey_id: str) -> RouteVerification:
        return self._placeholder_verification(journey_id, reason="rate_limited")

    def _schedule_verification(
        self,
        candidate: Dict[str, Any],
        travel_date: datetime,
        coach_preference: str,
        quota: str,
    ) -> None:
        async def _run():
            verification = await self._verify_route(candidate, travel_date, coach_preference, quota)
            key = self._cache_key(candidate["journey_id"], candidate.get("train_no", ""), travel_date, coach_preference, quota)
            if verification:
                self._store_cache(key, verification)

        task = asyncio.create_task(_run())
        self._pending_tasks.add(task)
        task.add_done_callback(lambda _: self._pending_tasks.discard(task))

    async def _verify_route(
        self,
        candidate: Dict[str, Any],
        travel_date: datetime,
        coach_preference: str,
        quota: str,
    ) -> Optional[RouteVerification]:
        train_no = candidate.get("train_no", "")
        if not train_no:
            return None

        date_str = travel_date.strftime("%Y-%m-%d") if isinstance(travel_date, datetime) else str(travel_date)
        live_task = asyncio.create_task(self._call_live(train_no))
        seat_task = asyncio.create_task(
            self._call_seat(
                train_no,
                date_str,
                candidate.get("from_code") or "",
                candidate.get("to_code") or "",
                coach_preference,
                quota,
            )
        )
        fare_task = asyncio.create_task(
            self._call_fare(
                train_no,
                candidate.get("from_code") or "",
                candidate.get("to_code") or "",
                coach_preference,
                quota,
                date_str,
            )
        )

        done, pending = await asyncio.wait(
            {live_task, seat_task, fare_task},
            timeout=self.total_timeout,
            return_when=asyncio.ALL_COMPLETED,
        )
        for pending_task in pending:
            pending_task.cancel()

        live = live_task.result() if live_task in done and not live_task.cancelled() else None
        seat = seat_task.result() if seat_task in done and not seat_task.cancelled() else None
        fare = fare_task.result() if fare_task in done and not fare_task.cancelled() else None

        errors: List[str] = []
        calls = {
            "live": live is not None,
            "seat": seat is not None,
            "fare": fare is not None,
        }
        if live and not live.get("success"):
            errors.append(live.get("error") or live.get("message") or "Live status reported issue")
        if seat and not seat.get("success"):
            errors.append(seat.get("error") or "Seat availability failed")
        if fare and not fare.get("success"):
            errors.append(fare.get("error") or "Fare verification failed")

        verified = bool(live and live.get("success") and seat and seat.get("success") and fare and fare.get("success"))
        return self._build_verification_result(
            journey_id=candidate["journey_id"],
            verified=verified,
            live=live,
            seat=seat,
            fare=fare,
            cached=False,
            errors=errors,
            verification_calls=calls,
        )

    def _cached_placeholder(self, verification: Dict[str, Any]) -> RouteVerification:
        return RouteVerification(
            journey_id=verification.get("journey_id", ""),
            verified=verification.get("verified", False),
            status=verification.get("status", "pending"),
            live_status=verification.get("live_status"),
            seat=verification.get("seat_availability"),
            fare=verification.get("fare"),
            delay_minutes=verification.get("delay_minutes"),
            confidence_score=verification.get("confidence_score", 0.0),
            cached=True,
            timestamp=verification.get("timestamp", datetime.utcnow().isoformat()),
            errors=verification.get("errors", []),
            verification_calls=verification.get("verification_calls", {"live": False, "seat": False, "fare": False}),
        )

    async def verify_top_routes(
        self,
        candidates: Iterable[Dict[str, Any]],
        travel_date: datetime,
        coach_preference: str = "AC_THREE_TIER",
        quota: str = "GN",
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for candidate in list(candidates)[:3]:
            cache_key = self._cache_key(candidate["journey_id"], candidate.get("train_no", ""), travel_date, coach_preference, quota)
            cached = self._get_cached(cache_key)
            if cached:
                results.append(cached)
                continue

            if not await self._acquire_rate_slot():
                results.append(self._rate_limited_verification(candidate["journey_id"]).to_dict())
                continue

            self._schedule_verification(candidate, travel_date, coach_preference, quota)
            results.append(self._placeholder_verification(candidate["journey_id"]).to_dict())

        return results