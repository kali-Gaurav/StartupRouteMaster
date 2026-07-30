"""
DASHBOARD SERVICE - User Dashboard Data Management
Production-ready with caching, pagination, indexing, and error handling.
Follows Feature #1 (Booking) patterns for consistency.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from collections import deque

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc, func
from sqlalchemy.exc import DBAPIError

from database.models import (
    User,
    Booking,
    Payment,
    PassengerDetails,
    BookingAuditLog
)
from services.cache.manager import CacheService
from core.resilience.core import circuit_breaker_manager, CircuitConfig, CircuitOpenError
from core.resilience.retry import RetryPolicy, RETRY_POLICY_DATABASE

logger = logging.getLogger(__name__)


# =========================================================================
# CONFIGURATION
# =========================================================================

@dataclass
class DashboardConfig:
    """Configuration for dashboard service."""
    cache_ttl_profile_hours: int = 1
    cache_ttl_summary_hours: int = 1
    cache_ttl_history_minutes: int = 30
    default_page_size: int = 50
    max_page_size: int = 100
    query_timeout_seconds: int = 5


@dataclass
class PaginationParams:
    """Pagination parameters for queries."""
    limit: int = 50
    offset: int = 0

    def validate(self):
        """Validate pagination parameters."""
        if self.limit < 1 or self.limit > 100:
            self.limit = 50
        if self.offset < 0:
            self.offset = 0


# =========================================================================
# DATA MODELS
# =========================================================================

@dataclass
class BookingHistoryItem:
    """Booking history item for dashboard."""
    booking_id: str
    pnr_number: Optional[str]
    status: str
    travel_date: Optional[date]
    from_station: Optional[str]
    to_station: Optional[str]
    amount_paid: float
    class_type: Optional[str]
    booked_at: datetime
    passenger_count: int


@dataclass
class PaymentHistoryItem:
    """Payment history item for dashboard."""
    payment_id: str
    booking_id: Optional[str]
    amount: float
    status: str
    method: Optional[str]
    created_at: datetime
    pnr_number: Optional[str] = None


@dataclass
class UserTicket:
    """User ticket for dashboard."""
    booking_id: str
    pnr_number: Optional[str]
    train_number: Optional[str]
    travel_date: Optional[date]
    status: str
    passengers: List[str]
    ticket_pdf_url: Optional[str]


@dataclass
class UserProfile:
    """User profile information."""
    user_id: str
    full_name: Optional[str]
    email: Optional[str]
    phone_number: Optional[str]
    member_since: datetime
    total_bookings: int
    total_spent: float
    preferences: Optional[Dict[str, Any]] = None


@dataclass
class DashboardSummary:
    """Dashboard summary statistics."""
    total_bookings: int
    total_spent: float
    upcoming_bookings: int
    completed_bookings: int
    cancelled_bookings: int
    pending_payments: int
    recent_activity: List[Dict[str, Any]]
    member_since: datetime
    last_booking_date: Optional[date]


class DashboardServiceMetrics:
    """Metrics tracking for dashboard service."""

    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)

    async def record_operation(self, operation: str, success: bool, duration_ms: float):
        """Record dashboard operation metrics."""
        self._metrics.append({
            "timestamp": datetime.utcnow(),
            "operation": operation,
            "success": success,
            "duration_ms": duration_ms
        })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}

        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_operation = {}

        for m in self._metrics:
            op = m["operation"]
            if op not in by_operation:
                by_operation[op] = {"total": 0, "success": 0}
            by_operation[op]["total"] += 1
            if m["success"]:
                by_operation[op]["success"] += 1

        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "by_operation": by_operation
        }


# =========================================================================
# DASHBOARD SERVICE
# =========================================================================

class DashboardService:
    """
    Dashboard service for user profile, booking history, payments, and tickets.

    Caching Strategy:
    - User profile: 1 hour cache
    - Dashboard summary: 1 hour cache
    - Booking/Payment history: 30 min cache
    - Cache keys are user-specific to prevent cross-user leakage

    Database Optimization:
    - Uses indexes on user_id, created_at, travel_date
    - Implements pagination to avoid N+1 queries
    - Prefetch passenger details and payment info
    """

    def __init__(self, db: Session, cache_service: CacheService = None):
        self.db = db
        self.cache = cache_service
        self.config = DashboardConfig()
        self.metrics = DashboardServiceMetrics()

        # Circuit breaker for external queries
        self.circuit_breaker = circuit_breaker_manager.get_breaker(
            "dashboard_db",
            CircuitConfig(
                failure_threshold=5,
                recovery_timeout_seconds=60,
                expected_exception=DBAPIError
            )
        )

    def _get_cache_key(self, user_id: str, key_type: str, extra: str = "") -> str:
        """Generate cache key for dashboard data."""
        base = f"dashboard:{user_id}:{key_type}"
        return f"{base}:{extra}" if extra else base

    # =========================================================================
    # BOOKING HISTORY
    # =========================================================================

    async def get_user_booking_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[BookingHistoryItem], int]:
        """
        Get all bookings for user with pagination.

        Args:
            user_id: User ID
            limit: Number of records to return (max 100)
            offset: Starting position

        Returns:
            Tuple of (booking list, total count)

        Features:
        - Pagination with limit/offset
        - Indexed queries on user_id and created_at
        - Passenger count aggregation
        - Cacheable results (30 min TTL)
        """
        pagination = PaginationParams(limit=limit, offset=offset)
        pagination.validate()

        start_time = datetime.utcnow()
        cache_key = self._get_cache_key(
            user_id,
            "bookings",
            f"{pagination.limit}_{pagination.offset}"
        )

        try:
            # Try cache first
            if self.cache:
                cached = await self._cache_get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for booking history: {user_id}")
                    return cached["items"], cached["total"]

            # Query with circuit breaker
            @self.circuit_breaker.wrap
            def _query_bookings():
                # Count total bookings
                total = self.db.query(func.count(Booking.id)).filter(
                    Booking.user_id == user_id
                ).scalar() or 0

                # Get paginated bookings with passenger details
                bookings = self.db.query(Booking).filter(
                    Booking.user_id == user_id
                ).options(
                    joinedload(Booking.passenger_details)
                ).order_by(
                    desc(Booking.created_at)
                ).limit(pagination.limit).offset(pagination.offset).all()

                return bookings, total

            bookings, total = await asyncio.get_event_loop().run_in_executor(
                None, _query_bookings
            )

            # Transform to response objects
            items = [
                BookingHistoryItem(
                    booking_id=b.id,
                    pnr_number=b.pnr_number,
                    status=b.booking_status,
                    travel_date=b.travel_date,
                    from_station=b.from_station_code,
                    to_station=b.to_station_code,
                    amount_paid=b.amount_paid or 0.0,
                    class_type=b.class_type,
                    booked_at=b.created_at,
                    passenger_count=len(b.passenger_details) if b.passenger_details else 0
                )
                for b in bookings
            ]

            # Cache results
            if self.cache:
                await self._cache_set(
                    cache_key,
                    {"items": items, "total": total},
                    ttl_minutes=self.config.cache_ttl_history_minutes
                )

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self.metrics.record_operation("get_booking_history", True, duration_ms)

            return items, total

        except Exception as e:
            logger.error(f"Error fetching booking history for {user_id}: {e}")
            await self.metrics.record_operation("get_booking_history", False, 0)
            return [], 0

    # =========================================================================
    # PAYMENT HISTORY
    # =========================================================================

    async def get_user_payment_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[PaymentHistoryItem], int]:
        """
        Get all payments for user with pagination.

        Args:
            user_id: User ID
            limit: Number of records to return
            offset: Starting position

        Returns:
            Tuple of (payment list, total count)

        Features:
        - Indexed query on user_id
        - Groups by booking
        - Includes payment method and status
        - 30 min cache TTL
        """
        pagination = PaginationParams(limit=limit, offset=offset)
        pagination.validate()

        start_time = datetime.utcnow()
        cache_key = self._get_cache_key(
            user_id,
            "payments",
            f"{pagination.limit}_{pagination.offset}"
        )

        try:
            # Try cache first
            if self.cache:
                cached = await self._cache_get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for payment history: {user_id}")
                    return cached["items"], cached["total"]

            # Query with circuit breaker
            @self.circuit_breaker.wrap
            def _query_payments():
                # Count total payments
                total = self.db.query(func.count(Payment.id)).filter(
                    Payment.user_id == user_id
                ).scalar() or 0

                # Get paginated payments with booking info
                payments = self.db.query(Payment).filter(
                    Payment.user_id == user_id
                ).options(
                    joinedload(Payment.booking)
                ).order_by(
                    desc(Payment.created_at)
                ).limit(pagination.limit).offset(pagination.offset).all()

                return payments, total

            payments, total = await asyncio.get_event_loop().run_in_executor(
                None, _query_payments
            )

            # Transform to response objects
            items = [
                PaymentHistoryItem(
                    payment_id=p.id,
                    booking_id=p.booking_id,
                    amount=p.amount,
                    status=p.status,
                    method=p.payment_method,
                    created_at=p.created_at,
                    pnr_number=p.booking.pnr_number if p.booking else None
                )
                for p in payments
            ]

            # Cache results
            if self.cache:
                await self._cache_set(
                    cache_key,
                    {"items": items, "total": total},
                    ttl_minutes=self.config.cache_ttl_history_minutes
                )

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self.metrics.record_operation("get_payment_history", True, duration_ms)

            return items, total

        except Exception as e:
            logger.error(f"Error fetching payment history for {user_id}: {e}")
            await self.metrics.record_operation("get_payment_history", False, 0)
            return [], 0

    # =========================================================================
    # TICKETS
    # =========================================================================

    async def get_user_tickets(self, user_id: str) -> List[UserTicket]:
        """
        Get all issued tickets for user.

        Args:
            user_id: User ID

        Returns:
            List of tickets with status and PNR info

        Features:
        - Status: active/expired/used
        - Sortable by travel date
        - Includes ticket PDF URL
        - No pagination (typically small number of active tickets)
        """
        start_time = datetime.utcnow()
        cache_key = self._get_cache_key(user_id, "tickets")

        try:
            # Try cache first
            if self.cache:
                cached = await self._cache_get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for tickets: {user_id}")
                    return cached

            # Query active and recent bookings
            @self.circuit_breaker.wrap
            def _query_tickets():
                # Get bookings with confirmed status (issued tickets)
                tickets = self.db.query(Booking).filter(
                    and_(
                        Booking.user_id == user_id,
                        Booking.booking_status.in_(["confirmed", "waitlist"])
                    )
                ).options(
                    joinedload(Booking.passenger_details)
                ).order_by(
                    desc(Booking.travel_date)
                ).all()

                return tickets

            tickets = await asyncio.get_event_loop().run_in_executor(
                None, _query_tickets
            )

            # Transform to response objects with status
            items = []
            today = date.today()

            for t in tickets:
                # Determine ticket status
                if t.travel_date < today:
                    status = "used"
                elif t.travel_date == today or (t.travel_date and (t.travel_date - today).days <= 3):
                    status = "active"
                else:
                    status = "upcoming"

                passenger_names = [p.full_name for p in t.passenger_details] if t.passenger_details else []

                items.append(
                    UserTicket(
                        booking_id=t.id,
                        pnr_number=t.pnr_number,
                        train_number=t.train_number,
                        travel_date=t.travel_date,
                        status=status,
                        passengers=passenger_names,
                        ticket_pdf_url=t.ticket_pdf_url
                    )
                )

            # Cache results
            if self.cache:
                await self._cache_set(
                    cache_key,
                    items,
                    ttl_minutes=self.config.cache_ttl_history_minutes
                )

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self.metrics.record_operation("get_tickets", True, duration_ms)

            return items

        except Exception as e:
            logger.error(f"Error fetching tickets for {user_id}: {e}")
            await self.metrics.record_operation("get_tickets", False, 0)
            return []

    # =========================================================================
    # USER PROFILE
    # =========================================================================

    async def get_user_profile(self, user_id: str) -> UserProfile:
        """
        Get user profile + preferences.

        Args:
            user_id: User ID

        Returns:
            User profile with membership info

        Features:
        - Includes name, email, phone, member_since
        - Aggregated booking/payment stats
        - User preferences
        - 1 hour cache TTL
        """
        start_time = datetime.utcnow()
        cache_key = self._get_cache_key(user_id, "profile")

        try:
            # Try cache first
            if self.cache:
                cached = await self._cache_get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for profile: {user_id}")
                    return cached

            # Query user and aggregated stats
            @self.circuit_breaker.wrap
            def _query_profile():
                user = self.db.query(User).filter(
                    User.id == user_id
                ).first()

                if not user:
                    return None

                # Get booking stats
                booking_stats = self.db.query(
                    func.count(Booking.id).label("total"),
                    func.sum(Booking.amount_paid).label("total_spent")
                ).filter(
                    Booking.user_id == user_id
                ).first()

                return {
                    "user": user,
                    "total_bookings": booking_stats.total or 0,
                    "total_spent": float(booking_stats.total_spent or 0.0)
                }

            result = await asyncio.get_event_loop().run_in_executor(
                None, _query_profile
            )

            if not result:
                raise ValueError(f"User {user_id} not found")

            user = result["user"]
            profile = UserProfile(
                user_id=user.id,
                full_name=user.full_name,
                email=user.email,
                phone_number=user.phone_number,
                member_since=user.created_at,
                total_bookings=result["total_bookings"],
                total_spent=result["total_spent"],
                preferences=user.preferences
            )

            # Cache results
            if self.cache:
                await self._cache_set(
                    cache_key,
                    profile,
                    ttl_minutes=self.config.cache_ttl_profile_hours * 60
                )

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self.metrics.record_operation("get_profile", True, duration_ms)

            return profile

        except Exception as e:
            logger.error(f"Error fetching profile for {user_id}: {e}")
            await self.metrics.record_operation("get_profile", False, 0)
            raise

    # =========================================================================
    # DASHBOARD SUMMARY
    # =========================================================================

    async def get_dashboard_summary(self, user_id: str) -> DashboardSummary:
        """
        Get dashboard summary (totals, status counts).

        Args:
            user_id: User ID

        Returns:
            Dashboard summary with statistics

        Features:
        - Total bookings, total spent
        - Upcoming vs completed booking counts
        - Pending payment count
        - Recent activity feed
        - 1 hour cache TTL
        """
        start_time = datetime.utcnow()
        cache_key = self._get_cache_key(user_id, "summary")

        try:
            # Try cache first
            if self.cache:
                cached = await self._cache_get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for summary: {user_id}")
                    return cached

            # Query aggregated statistics
            @self.circuit_breaker.wrap
            def _query_summary():
                today = date.today()

                # Total stats
                booking_stats = self.db.query(
                    func.count(Booking.id).label("total"),
                    func.sum(Booking.amount_paid).label("total_spent")
                ).filter(
                    Booking.user_id == user_id
                ).first()

                # Upcoming bookings (travel_date >= today)
                upcoming = self.db.query(func.count(Booking.id)).filter(
                    and_(
                        Booking.user_id == user_id,
                        Booking.travel_date >= today
                    )
                ).scalar() or 0

                # Completed bookings (travel_date < today, confirmed/completed status)
                completed = self.db.query(func.count(Booking.id)).filter(
                    and_(
                        Booking.user_id == user_id,
                        Booking.travel_date < today,
                        Booking.booking_status.in_(["confirmed", "completed"])
                    )
                ).scalar() or 0

                # Cancelled bookings
                cancelled = self.db.query(func.count(Booking.id)).filter(
                    and_(
                        Booking.user_id == user_id,
                        Booking.booking_status == "cancelled"
                    )
                ).scalar() or 0

                # Pending payments
                pending_payments = self.db.query(func.count(Payment.id)).filter(
                    and_(
                        Payment.user_id == user_id,
                        Payment.status == "pending"
                    )
                ).scalar() or 0

                # Get user for member_since
                user = self.db.query(User).filter(
                    User.id == user_id
                ).first()

                # Recent activity (last 5 bookings)
                recent_bookings = self.db.query(Booking).filter(
                    Booking.user_id == user_id
                ).order_by(
                    desc(Booking.created_at)
                ).limit(5).all()

                return {
                    "total_bookings": booking_stats.total or 0,
                    "total_spent": float(booking_stats.total_spent or 0.0),
                    "upcoming": upcoming,
                    "completed": completed,
                    "cancelled": cancelled,
                    "pending_payments": pending_payments,
                    "user_member_since": user.created_at if user else datetime.utcnow(),
                    "last_booking_date": recent_bookings[0].travel_date if recent_bookings else None,
                    "recent_bookings": recent_bookings
                }

            result = await asyncio.get_event_loop().run_in_executor(
                None, _query_summary
            )

            # Build recent activity feed
            recent_activity = []
            for booking in result["recent_bookings"]:
                recent_activity.append({
                    "type": "booking",
                    "booking_id": booking.id,
                    "pnr": booking.pnr_number,
                    "status": booking.booking_status,
                    "date": booking.created_at.isoformat(),
                    "amount": booking.amount_paid
                })

            summary = DashboardSummary(
                total_bookings=result["total_bookings"],
                total_spent=result["total_spent"],
                upcoming_bookings=result["upcoming"],
                completed_bookings=result["completed"],
                cancelled_bookings=result["cancelled"],
                pending_payments=result["pending_payments"],
                recent_activity=recent_activity,
                member_since=result["user_member_since"],
                last_booking_date=result["last_booking_date"]
            )

            # Cache results
            if self.cache:
                await self._cache_set(
                    cache_key,
                    summary,
                    ttl_minutes=self.config.cache_ttl_summary_hours * 60
                )

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self.metrics.record_operation("get_summary", True, duration_ms)

            return summary

        except Exception as e:
            logger.error(f"Error fetching summary for {user_id}: {e}")
            await self.metrics.record_operation("get_summary", False, 0)
            raise

    # =========================================================================
    # CACHE HELPERS
    # =========================================================================

    async def _cache_get(self, key: str) -> Optional[Any]:
        """Get value from cache with error handling."""
        try:
            if self.cache:
                return await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.cache.get(key)
                )
        except Exception as e:
            logger.warning(f"Cache get error for {key}: {e}")
        return None

    async def _cache_set(self, key: str, value: Any, ttl_minutes: int) -> bool:
        """Set value in cache with error handling."""
        try:
            if self.cache:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.cache.set(
                        key,
                        value,
                        ttl=ttl_minutes * 60  # Convert to seconds
                    )
                )
                return True
        except Exception as e:
            logger.warning(f"Cache set error for {key}: {e}")
        return False

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def invalidate_user_cache(self, user_id: str):
        """Invalidate all cache entries for a user."""
        if not self.cache:
            return

        keys_to_delete = [
            self._get_cache_key(user_id, "profile"),
            self._get_cache_key(user_id, "summary"),
            self._get_cache_key(user_id, "tickets")
        ]

        # Also invalidate paginated history keys
        for i in range(0, 5):  # Invalidate first 5 pages
            for limit in [50, 100]:
                keys_to_delete.append(
                    self._get_cache_key(user_id, "bookings", f"{limit}_{i * limit}")
                )
                keys_to_delete.append(
                    self._get_cache_key(user_id, "payments", f"{limit}_{i * limit}")
                )

        for key in keys_to_delete:
            try:
                if self.cache:
                    self.cache.delete(key)
            except Exception as e:
                logger.warning(f"Cache invalidation error for {key}: {e}")

    def get_metrics(self) -> dict:
        """Get service metrics."""
        return self.metrics.get_metrics()


# =========================================================================
# DEPENDENCY INJECTION
# =========================================================================

def get_dashboard_service(db: Session, cache_service: CacheService = None) -> DashboardService:
    """Dependency injection for dashboard service."""
    return DashboardService(db, cache_service)
