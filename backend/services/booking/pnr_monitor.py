"""
PNR Monitor Service - Long-Polling PNR Status Monitoring
=========================================================

[Task 4.3] Long-polling PNR Monitor.
Periodically checks the live status of all PNRs in the system.

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from collections import deque
from sqlalchemy.orm import Session
from database.session import SessionUser, init_db
from database.models import Booking, BookingStatus, AuditLog

from core.resilience.core import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy

logger = logging.getLogger("pnr-monitor")


@dataclass
class PNRStatus:
    """PNR status result."""
    pnr_number: str
    train_number: str
    status: str
    delay_minutes: int = 0
    issues: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)


class PNRMonitorService:
    """
    [Task 4.3] Long-polling PNR Monitor.
    Periodically checks the live status of all PNRs in the system.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize PNR monitor service with resilience patterns."""
        self._is_running = False
        
        # Circuit breaker for verification service calls
        self._verification_breaker = circuit_breaker_manager.get_or_create(
            "pnr_monitor_verification",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=3
            )
        )
        
        # Retry policy for verification calls
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Monitoring statistics
        self._stats = {
            "bookings_checked": 0,
            "status_changes": 0,
            "cancellations": 0,
            "errors": 0
        }
        self._stats_lock = asyncio.Lock()
        
        # Throttle settings
        self._throttle_delay = 2.0  # seconds between requests
        
        logger.info("PNRMonitorService initialized with resilience patterns")

    async def poll_active_pnrs(self, limit: int = 100) -> Dict[str, Any]:
        """
        Background task to refresh PNR statuses.
        
        Args:
            limit: Maximum bookings to process
            
        Returns:
            Dict with monitoring results
        """
        if self._is_running:
            return {"status": "SKIPPED", "reason": "ALREADY_RUNNING"}
        
        self._is_running = True
        start_time = datetime.utcnow()
        results = {
            "status": "COMPLETED",
            "start_time": start_time.isoformat(),
            "bookings_checked": 0,
            "status_changes": 0,
            "cancellations": 0,
            "errors": 0,
            "duration_seconds": 0
        }
        
        try:
            logger.info("📡 Starting PNR Monitoring Cycle...")
            
            with SessionUser() as db:
                # Find bookings that are active and not travelled yet
                active_bookings = db.query(Booking).filter(
                    Booking.booking_status.in_([
                        "confirmed", "pending", "waitlist", "WAITLIST", 
                        "CONFIRMED", "PENDING"
                    ]),
                    Booking.pnr_number != None
                ).limit(limit).all()
                
                logger.info(f"Found {len(active_bookings)} PNRs to monitor.")
                
                for b in active_bookings:
                    try:
                        # Fetch Live Verification with circuit breaker protection
                        status = await self._verify_booking(b)
                        
                        # Update status if changed
                        if status:
                            await self._update_booking_status(db, b, status)
                            results["status_changes"] += 1
                            
                            if status.status.lower() == "cancelled":
                                results["cancellations"] += 1
                        
                        results["bookings_checked"] += 1
                        
                        # Throttle to avoid rate limiting
                        await asyncio.sleep(self._throttle_delay)
                        
                    except Exception as e:
                        logger.error(f"Failed to poll PNR {b.pnr_number}: {e}")
                        results["errors"] += 1
                        
                        async with self._stats_lock:
                            self._stats["errors"] += 1
                
                db.commit()
            
            # Update stats
            async with self._stats_lock:
                self._stats["bookings_checked"] = results["bookings_checked"]
                self._stats["status_changes"] = results["status_changes"]
                self._stats["cancellations"] = results["cancellations"]
            
            # Record metrics
            await self._record_metrics("poll_cycle", True, results["bookings_checked"])
            
            logger.info(
                f"✅ PNR Monitoring Cycle Complete: {results['bookings_checked']} checked, "
                f"{results['status_changes']} changes, {results['cancellations']} cancellations"
            )
            
        except Exception as e:
            logger.error(f"❌ PNR Monitor Fail: {e}")
            results["status"] = "FAILED"
            results["error"] = str(e)
            await self._record_metrics("poll_cycle", False, 0)
            
        finally:
            self._is_running = False
            results["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
        
        return results

    async def _verify_booking(self, booking: Booking) -> Optional[PNRStatus]:
        """
        Verify a single booking status.
        
        Args:
            booking: Booking instance
            
        Returns:
            PNRStatus or None
        """
        from services.booking_verification_service import booking_verification_service
        
        async def _do_verify():
            """Internal verification logic."""
            return await booking_verification_service.verify_booking_details(
                pnr_number=booking.pnr_number,
                train_number=booking.train_number,
                travel_date=booking.travel_date.strftime("%Y-%m-%d") if booking.travel_date else None
            )
        
        try:
            result = await self._verification_breaker.execute(
                self._retry_policy.execute,
                _do_verify
            )
            
            if result and result.get("pnr_status"):
                pnr_status = result["pnr_status"]
                return PNRStatus(
                    pnr_number=str(booking.pnr_number or ""),
                    train_number=str(booking.train_number or ""),
                    status=pnr_status.get("status", "UNKNOWN"),
                    delay_minutes=pnr_status.get("delay_minutes", 0),
                    issues=result.get("issues", [])
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Verification failed for {booking.pnr_number}: {e}")
            return None

    async def _update_booking_status(
        self,
        db: Session,
        booking: Booking,
        status: PNRStatus
    ):
        """
        Update booking status if changed.
        
        Args:
            db: Database session
            booking: Booking instance
            status: New PNR status
        """
        new_status = status.status.lower()
        old_status = booking.booking_status.lower() if booking.booking_status else ""
        
        if new_status != old_status:
            logger.info(
                f"PNR Status Change detected for {booking.pnr_number}: "
                f"{booking.booking_status} -> {status.status}"
            )
            
            # Log the change
            audit = AuditLog(
                entity_type="Booking",
                entity_id=booking.id,
                action="PNR_MONITOR_UPDATE",
                old_value=booking.booking_status,
                new_value=status.status,
                reason=f"Status updated via auto-polling. Delay: {status.delay_minutes}m"
            )
            db.add(audit)
            
            # Update booking status
            booking.booking_status = status.status
            
            # Handle cancellations
            if "cancelled" in new_status or "cancelled" in str(status.issues):
                booking.booking_status = "cancelled"
                # Additional cancellation handling would go here

    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        return {
            "is_running": self._is_running,
            "stats": dict(self._stats),
            "throttle_delay": self._throttle_delay
        }

    def start(self):
        """Start the monitoring service."""
        self._is_running = True

    def stop(self):
        """Stop the monitoring service."""
        self._is_running = False

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        operation_type: str,
        success: bool,
        bookings_checked: int = 0
    ):
        """Record operation metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "bookings_checked": bookings_checked
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
            "status_changes": self._stats["status_changes"],
            "cancellations": self._stats["cancellations"],
            "errors": self._stats["errors"],
            "is_running": self._is_running,
            "circuit_breaker_state": self._verification_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "is_running": self._is_running,
            "circuit_breaker": {
                "state": self._verification_breaker.get_state().value,
                "failure_count": self._verification_breaker.failure_count,
                "success_count": self._verification_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._verification_breaker.reset()
        logger.info("Circuit breaker reset for PNR monitor service")


# Global instance
pnr_monitor_service = PNRMonitorService()
