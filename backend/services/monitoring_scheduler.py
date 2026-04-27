"""
Monitoring Scheduler - Background Booking Monitoring Service
============================================================

Task 15: Background Monitoring Scheduler.
Identifies bookings needing status updates, fetches fresh data from Provider Gateway,
detects changes in status (delays, cancellations, PNR updates), and triggers alerts.

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import asyncio
import inspect
import logging
import json
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from sqlalchemy import select, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BookingMonitor
from providers.gateway import provider_gateway
from providers.models import AlertMessage, UnifiedLiveStatus
from core.redis_client import async_redis_client
from database.session import AsyncSessionUser

from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy

logger = logging.getLogger("routemaster.monitoring")


class AlertPriority(Enum):
    """Alert priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QueuedAlert:
    """Alert queued for processing."""
    alert_id: str
    user_id: str
    booking_id: str
    alert_type: str
    details: Dict[str, Any]
    priority: AlertPriority
    queued_at: datetime
    retry_count: int = 0


class AlertQueueService:
    """
    Service for reliably queuing alerts into Redis for consumption by 
    notification workers (Telegram, Push, SMS).
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self, redis_client=None):
        """Initialize alert queue service with resilience patterns."""
        self.redis = redis_client or async_redis_client
        self.queue_name = "booking_alerts_queue"
        
        # Circuit breaker for Redis operations
        self._redis_breaker = circuit_breaker_manager.get_or_create(
            "alert_queue_redis",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=10.0,
                success_threshold=3
            )
        )
        
        # Retry policy for operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=2.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Local queue fallback
        self._local_queue: deque = deque(maxlen=1000)
        self._local_lock = asyncio.Lock()
        
        logger.info("AlertQueueService initialized with resilience patterns")

    async def queue_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Submits a validated alert to the Redis queue.
        
        Args:
            alert_data: Alert data dictionary
            
        Returns:
            True if queued successfully
            
        Protected by circuit breaker with local fallback.
        """
        try:
            # Validate with Pydantic model
            alert = AlertMessage(**alert_data)
            payload = alert.model_dump_json() if hasattr(alert, 'model_dump_json') else alert.json()
            
            async def _do_queue():
                """Internal queue logic."""
                client = await self.redis.get_client()
                result = client.rpush(self.queue_name, payload)
                if inspect.isawaitable(result):
                    await result
            
            await self._redis_breaker.execute(
                self._retry_policy.execute,
                _do_queue
            )
            
            logger.info(
                f"🔔 Alert queued for booking {alert.booking_id} "
                f"(Type: {alert.alert_type})"
            )
            
            await self._record_metrics("alert_queued", True, alert.alert_type)
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to queue alert: {e}", exc_info=True)
            
            # Fallback to local queue
            await self._queue_local(alert_data)
            await self._record_metrics("alert_queued", True, "local_fallback")
            return True

    async def _queue_local(self, alert_data: Dict[str, Any]):
        """Queue alert to local fallback."""
        async with self._local_lock:
            self._local_queue.append(
                QueuedAlert(
                    alert_id=alert_data.get("alert_id", str(datetime.utcnow().timestamp())),
                    user_id=alert_data.get("user_id", ""),
                    booking_id=alert_data.get("booking_id", ""),
                    alert_type=alert_data.get("alert_type", "unknown"),
                    details=alert_data.get("details", {}),
                    priority=AlertPriority(alert_data.get("priority", "normal")),
                    queued_at=datetime.utcnow()
                )
            )

    async def get_queue_length(self) -> int:
        """Get current queue length."""
        try:
            client = await self.redis.get_client()
            result = client.llen(self.queue_name)
            if inspect.isawaitable(result):
                return await result
            return result
        except Exception:
            return len(self._local_queue)

    async def retry_failed_alerts(self) -> int:
        """
        Retry alerts that failed to queue.
        
        Returns:
            Number of alerts retried
        """
        retried = 0
        
        async with self._local_lock:
            failed_alerts = list(self._local_queue)
            self._local_queue.clear()
        
        for alert_data in failed_alerts:
            try:
                await self.queue_alert(alert_data.__dict__ if hasattr(alert_data, '__dict__') else alert_data)
                retried += 1
            except Exception as e:
                logger.error(f"❌ Retry failed for alert: {e}")
        
        if retried > 0:
            logger.info(f"🔄 Retried {retried} failed alerts")
        
        return retried

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        operation_type: str,
        success: bool,
        alert_type: str = ""
    ):
        """Record operation metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "alert_type": alert_type
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            a_type = m.get("alert_type", "unknown")
            by_type[a_type] = by_type.get(a_type, 0) + 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "alert_type_breakdown": by_type,
            "local_queue_size": len(self._local_queue),
            "circuit_breaker_state": self._redis_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "redis_available": self.redis is not None,
            "circuit_breaker": {
                "state": self._redis_breaker.get_state().value,
                "failure_count": self._redis_breaker.failure_count,
                "success_count": self._redis_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._redis_breaker.reset()
        logger.info("Circuit breaker reset for alert queue service")


class BookingMonitorService:
    """
    Task 15: Background Monitoring Scheduler.
    Identifies bookings needing status updates, fetches fresh data from Provider Gateway,
    detects changes in status (delays, cancellations, PNR updates), and triggers alerts.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self, alert_queue: AlertQueueService):
        """Initialize booking monitor service with resilience patterns."""
        self.alert_queue = alert_queue
        
        # Frequencies based on proximity to travel
        self.active_check_interval = timedelta(minutes=15)
        self.upcoming_check_interval = timedelta(hours=1)
        self.monitoring_window_hours = 48
        self._is_running = False
        
        # Circuit breaker for gateway operations
        self._gateway_breaker = circuit_breaker_manager.get_or_create(
            "booking_monitor_gateway",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=3
            )
        )
        
        # Retry policy for gateway operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Monitoring statistics
        self._stats = {
            "bookings_checked": 0,
            "alerts_triggered": 0,
            "errors": 0
        }
        self._stats_lock = asyncio.Lock()
        
        logger.info("BookingMonitorService initialized with resilience patterns")

    async def get_bookings_for_monitoring(self, session: AsyncSession) -> List[BookingMonitor]:
        """
        Queries the database for bookings requiring a fresh check.
        Criteria:
        - Monitoring is active
        - Within travel date window (Yesterday to +2 days)
        - Last check time is older than the required interval
        """
        now = datetime.utcnow()
        today = now.date()
        
        active_cutoff = now - self.active_check_interval
        upcoming_cutoff = now - self.upcoming_check_interval
        window_start = today - timedelta(days=1)
        window_end = today + timedelta(days=2)

        # Build dynamic query
        query = select(BookingMonitor).where(
            and_(
                BookingMonitor.is_monitoring_active == True,
                BookingMonitor.travel_date.between(window_start, window_end),
                or_(
                    BookingMonitor.last_check_timestamp == None,  # Never checked
                    and_(
                        BookingMonitor.travel_date == today,
                        BookingMonitor.last_check_timestamp < active_cutoff
                    ),
                    and_(
                        BookingMonitor.travel_date > today,
                        BookingMonitor.last_check_timestamp < upcoming_cutoff
                    )
                )
            )
        ).limit(100)  # Process in batches

        result = await session.execute(query)
        return list(result.scalars().all())

    async def detect_changes(
        self,
        booking: BookingMonitor,
        latest_live: Optional[UnifiedLiveStatus],
        latest_pnr: Optional[Dict[str, Any]]
    ):
        """
        Compares latest data fetch against stored snapshots in the database.
        Triggers an alert if significant deviations are found.
        """
        alert_triggered = False
        alert_details = []
        alert_type = "booking_update"

        # 1. LIVE STATUS CHANGE DETECTION
        if latest_live:
            last_live = booking.last_known_live_status or {}
            
            # Detect Running Status Changes
            if latest_live.running_status != last_live.get("running_status"):
                alert_details.append(f"Train status update: {latest_live.running_status}")
                alert_triggered = True
                if latest_live.running_status == "Cancelled":
                    alert_type = "cancellation"

            # Detect Delay Escalation
            delay_threshold = booking.alert_preferences.get("notify_on_delay_minutes", 60)
            if latest_live.delay_minutes > delay_threshold and last_live.get("delay_minutes", 0) <= delay_threshold:
                alert_details.append(f"Delay crossed threshold ({delay_threshold}m): Currently {latest_live.delay_minutes}m late.")
                alert_triggered = True
                alert_type = "delay_warning"

            # Snapshot current status
            booking.last_known_live_status = latest_live.model_dump()

        # 2. PNR STATUS CHANGE DETECTION
        if latest_pnr:
            last_pnr = booking.last_known_pnr_status or {}
            
            # Detect Booking Status confirmation
            current_status = latest_pnr.get("booking_status") or latest_pnr.get("reservation_status", "Unknown")
            old_status = last_pnr.get("booking_status") or last_pnr.get("reservation_status", "Unknown")
            
            if current_status != old_status:
                alert_details.append(f"PNR status change: {old_status} ➔ {current_status}")
                alert_triggered = True
                if "CNF" in str(current_status).upper():
                    alert_type = "pnr_confirmation"

            # Detect Chart Preparation
            if latest_pnr.get("chart_prepared") and not last_pnr.get("chart_prepared"):
                alert_details.append("Chart has been prepared for your journey. Check your coach assignment.")
                alert_triggered = True
                alert_type = "chart_prepared"

            # Snapshot current PNR status
            booking.last_known_pnr_status = latest_pnr

        # 3. TRIGGER ALERT QUEUING
        if alert_triggered:
            import uuid
            alert_msg = {
                "alert_id": str(uuid.uuid4()),
                "user_id": booking.user_id,
                "booking_id": booking.booking_id,
                "alert_type": alert_type,
                "details": {
                    "message": " | ".join(alert_details),
                    "train_number": booking.train_number,
                    "pnr_number": booking.pnr_number,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "priority": "high" if alert_type in ["cancellation", "pnr_confirmation"] else "normal"
            }
            await self.alert_queue.queue_alert(alert_msg)
            
            async with self._stats_lock:
                self._stats["alerts_triggered"] += 1

    async def _process_booking(self, booking: BookingMonitor, session: AsyncSession):
        """Worker function for a single booking."""
        try:
            logger.debug(f"🔍 Monitoring check for {booking.booking_id}...")
            
            # Fetch from Gateway with circuit breaker protection
            if booking.train_number and booking.travel_date:
                train_number = booking.train_number
                travel_date = booking.travel_date
                async def _fetch_live():
                    return await provider_gateway.get_live_status(
                        train_number,
                        travel_date.isoformat()
                    )

                live_task = self._gateway_breaker.execute(
                    self._retry_policy.execute,
                    _fetch_live
                )
            else:
                live_task = asyncio.sleep(0, result=None)
            
            # PNR can be fetched if number is present
            if booking.pnr_number:
                pnr_number = booking.pnr_number
                async def _fetch_pnr():
                    return await provider_gateway.get_pnr_status(pnr_number)
                
                pnr_task = self._gateway_breaker.execute(
                    self._retry_policy.execute,
                    _fetch_pnr
                )
            else:
                pnr_task = asyncio.sleep(0, result=None)

            latest_live, latest_pnr = await asyncio.gather(live_task, pnr_task)
            
            # Perform change detection
            await self.detect_changes(booking, latest_live, latest_pnr)
            
            # Update last check mark
            booking.last_check_timestamp = datetime.utcnow()
            
            async with self._stats_lock:
                self._stats["bookings_checked"] += 1
            
        except Exception as e:
            logger.error(f"Error processing booking {booking.booking_id}: {e}", exc_info=True)
            async with self._stats_lock:
                self._stats["errors"] += 1

    async def run_scheduler_loop(self, interval_seconds: int = 600):
        """
        Active polling loop.
        Can be registered with the central background task orchestrator.
        """
        self._is_running = True
        logger.info(f"🛰️ Monitoring Scheduler Service Online (Interval: {interval_seconds}s)")
        
        while self._is_running:
            run_start = datetime.utcnow()
            try:
                # Use AsyncSessionUser for user-store queries
                async with AsyncSessionUser() as session:
                    # Fetch candidates
                    bookings = await self.get_bookings_for_monitoring(session)
                    
                    if bookings:
                        logger.info(f"📊 Run active: checking {len(bookings)} bookings.")
                        # Parallel execution for the batch
                        await asyncio.gather(
                            *[self._process_booking(b, session) for b in bookings]
                        )
                        # Commit all updates to last_known_status and timestamps
                        await session.commit()
                    else:
                        logger.debug("💤 No monitoring tasks in this run.")
                
                # Record metrics
                await self._record_metrics("scheduler_cycle", True)
                
            except Exception as e:
                logger.error(f"🆘 Monitoring Scheduler Failure: {e}", exc_info=True)
                await self._record_metrics("scheduler_cycle", False)
                await asyncio.sleep(10)  # Cooldown on failure

            # Dynamic sleep based on execution time
            elapsed = (datetime.utcnow() - run_start).total_seconds()
            sleep_time = max(10, interval_seconds - elapsed)
            await asyncio.sleep(sleep_time)

    def stop(self):
        """Stop the monitoring loop."""
        self._is_running = False

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(self, operation_type: str, success: bool):
        """Record operation metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "bookings_checked": self._stats["bookings_checked"],
            "alerts_triggered": self._stats["alerts_triggered"],
            "errors": self._stats["errors"],
            "is_running": self._is_running,
            "circuit_breaker_state": self._gateway_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "is_running": self._is_running,
            "circuit_breaker": {
                "state": self._gateway_breaker.get_state().value,
                "failure_count": self._gateway_breaker.failure_count,
                "success_count": self._gateway_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._gateway_breaker.reset()
        logger.info("Circuit breaker reset for booking monitor service")


# --- Global Orchestration Singleton ---
alert_queue = AlertQueueService()
monitoring_scheduler = BookingMonitorService(alert_queue)


# Hook for application startup
async def start_monitoring_daemon():
    """Entry point to start the background monitoring loop."""
    asyncio.create_task(monitoring_scheduler.run_scheduler_loop())
