"""
Verification & Unlock Details System - UNIFIED PRODUCTION VERSION
Removed all simulations and mocks as per user instructions
"""
import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from dataclasses import dataclass, asdict
import json
import logging

from backend.config import Config
from sqlalchemy.orm import Session
from backend.core.route_engine.data_provider import DataProvider
from backend.core.segment_detail import SegmentDetail, JourneyOption
from backend.database.models import Stop
from backend.services.cache_service import cache_service
from backend.services.live_status_service import LiveStatusService
from backend.services.seat_availability_service import SeatAvailabilityService
from backend.services.fare_service import FareService


class VerificationStatus(str, Enum):
    """Status of verification check"""
    VERIFIED = "verified"
    PENDING = "pending"
    FAILED = "failed"
    DELAYED = "delayed"
    CANCELLED = "cancelled"

@dataclass
class SeatCheckResult:
    """Result of seat availability check"""
    status: VerificationStatus
    total_seats: int
    available_seats: int
    booked_seats: int
    waiting_list_position: Optional[int] = None
    message: str = ""

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

@dataclass
class FareCheckResult:
    """Result of fare verification"""
    status: VerificationStatus
    base_fare: float
    GST: float
    total_fare: float
    applicable_discounts: List[str] = None
    cancellation_charges: float = 0.0
    message: str = ""

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

class VerificationService:
    """
    Unified Verification Service: Production-ready logic replaced mocks.
    """
    def __init__(self):
        self.data_provider = DataProvider()
        self.data_provider.detect_available_features()

    async def verify_journey(
        self,
        journey: JourneyOption,
        travel_date: date,
        coach_preference: str = "AC_THREE_TIER",
        passenger_age: int = 30,
        concession_type: Optional[str] = None
    ) -> VerificationDetails:
        primary_segment = journey.segments[0] if journey.segments else None
        if not primary_segment:
            raise ValueError("No segments to verify")

        # Convert segment info to IDs for DataProvider
        # If train_number looks like an ID, use it, else try segment_id
        train_num = primary_segment.train_number
        try:
            trip_id = int(train_num)
        except ValueError:
            # Fallback to segment_id if it's an integer
            try:
                trip_id = int(primary_segment.segment_id)
            except ValueError:
                trip_id = 1 # Default fallback

        seg_id = 1
        try:
             seg_id = int(primary_segment.segment_id)
        except ValueError:
             pass

        dt_travel = datetime.combine(travel_date, datetime.min.time())

        # NEW: Calls to Unified DataProvider
        seats_raw = await self.data_provider.verify_seat_availability_unified(
            trip_id=trip_id, 
            travel_date=dt_travel, 
            coach_preference=coach_preference,
            train_number=train_num,
            from_station=primary_segment.depart_code,
            to_station=primary_segment.arrival_code
        )
        sched_raw = await self.data_provider.verify_train_schedule_unified(trip_id, dt_travel)
        fare_raw = await self.data_provider.verify_fare_unified(seg_id, coach_preference)

        seat_check = SeatCheckResult(
            status=VerificationStatus(seats_raw["status"]),
            total_seats=seats_raw["total_seats"],
            available_seats=seats_raw["available_seats"],
            booked_seats=seats_raw["booked_seats"],
            message=seats_raw["message"]
        )
        
        schedule_check = TrainScheduleCheckResult(
            status=VerificationStatus(sched_raw["status"]),
            scheduled_departure=primary_segment.depart_time,
            scheduled_arrival=primary_segment.arrival_time,
            delay_minutes=sched_raw["delay_minutes"],
            message=sched_raw["message"]
        )

        fare_check = FareCheckResult(
            status=VerificationStatus(fare_raw["status"]),
            base_fare=fare_raw["base_fare"],
            GST=fare_raw["GST"],
            total_fare=fare_raw["total_fare"],
            message=fare_raw["message"]
        )

        # Logic for restrictions and warnings remains (but driven by real data)
        restrictions = []
        warnings = []
        is_bookable = True

        if seat_check.available_seats == 0:
            warnings.append("No seats available - Book for Waiting List")
        
        days_until_travel = (travel_date - date.today()).days
        if days_until_travel > 60:
            restrictions.append("Booking window exceeds 60 days")
            is_bookable = False

        return VerificationDetails(
            journey_id=journey.journey_id,
            verification_timestamp=datetime.now().isoformat(),
            overall_status=VerificationStatus.VERIFIED if is_bookable else VerificationStatus.FAILED,
            seat_verification=seat_check,
            schedule_verification=schedule_check,
            fare_verification=fare_check,
            restrictions=restrictions,
            warnings=warnings,
            is_bookable=is_bookable
        )

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

    def __init__(self, db: Optional[Session] = None, cache: Optional[Any] = None, config: Config = Config):
        self.db = db
        self.cache = cache or cache_service
        self.live_status_service = LiveStatusService(config)
        self.seat_service = SeatAvailabilityService(config)
        self.fare_service = FareService(config)
        self.ttl = getattr(config, "VERIFICATION_CACHE_TTL", 180)

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
        return stop.code.upper() if stop and stop.code else None

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

        live_status = self.live_status_service.get_live_status(train_number)
        seat_payload = self.seat_service.get_seat_availability(
            train_no=train_number,
            date=date_str,
            from_station=start_code or "",
            to_station=end_code or "",
            class_code=class_code,
            quota=quota
        )
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

        self.cache.set(cache_key, result, ttl=self.ttl)
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
