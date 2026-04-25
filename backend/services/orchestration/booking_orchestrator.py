import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from services.booking_service import BookingService
from services.booking_verification_service import booking_verification_service
from services.agents.flex_route_agent import flex_route_agent
from services.agents.queue_warden import queue_warden
from services.cache_service import cache_service
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("orchestrator.booking")

class BookingOrchestrator:
    """
    [Group 1] Intelligent Booking Orchestrator.
    Manages the end-to-end booking workflow with AI-driven failure recovery.
    Integrates Flex-Route Agent for 'Sold Out' scenarios.
    """
    def __init__(self, db: Session):
        self.db = db
        self.booking_svc = BookingService(db)
        # Circuit breaker for booking operations
        self._booking_circuit_breaker = circuit_breaker(
            name="booking_orchestrator",
            failure_threshold=5,
            recovery_timeout=60.0
        )
        # Circuit breaker for flex fallback
        self._flex_fallback_circuit_breaker = circuit_breaker(
            name="flex_fallback",
            failure_threshold=3,
            recovery_timeout=120.0
        )
        # Retry policies
        self._booking_retry_policy = retry_policy(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=0.5,
            max_delay=10.0
        )
        self._verification_retry_policy = retry_policy(
            max_attempts=2,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            base_delay=0.2,
            max_delay=2.0
        )
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name="booking_orchestrator",
            default_tags={"component": "orchestration"}
        )
        self._metrics.gauge("booking_circuit_breaker_state", lambda: self._booking_circuit_breaker.state.value)
        self._metrics.gauge("flex_fallback_circuit_breaker_state", lambda: self._flex_fallback_circuit_breaker.state.value)
        self._metrics.counter("bookings_total")
        self._metrics.counter("bookings_success")
        self._metrics.counter("bookings_failed")
        self._metrics.counter("flex_fallbacks_total")
        self._metrics.counter("hold_success_total")
        self._metrics.counter("hold_expired_total")
        self._metrics.histogram("booking_duration_seconds")
        self._metrics.histogram("hold_duration_seconds")

    async def prepare_standoff_hold(self, user_id: str, route_payload: Dict) -> Dict:
        """
        [G1.3.1.1] Predictive 'Standoff' Hold.
        Soft-locks inventory BEFORE payment to ensure conversion for high-demand seats.
        """
        start_time = time.perf_counter()
        train_number = route_payload.get("train_number")
        source = route_payload.get("source")
        destination = route_payload.get("destination")
        travel_date = route_payload.get("travel_date")
        class_code = route_payload.get("class_code")

        from database.models import SeatInventory, Trip, Booking, EscrowStatus
        
        try:
            # 1. Atomic Check & Lock
            trip = self.db.query(Trip).filter(Trip.trip_id == train_number).first()
            if not trip:
                return {"status": "FAILED", "reason": "TRIP_NOT_FOUND"}

            inventory = self.db.query(SeatInventory).filter(
                SeatInventory.trip_id == trip.id,
                SeatInventory.travel_date == travel_date,
                SeatInventory.coach_type == class_code
            ).with_for_update().first()

            if not inventory or inventory.available_seats <= 0:
                logger.warning(f"⚠️ [STANDOFF] Sold Out for {train_number}. Triggering Arbitrage check.")
                return await self._trigger_flex_fallback(source, destination, travel_date, train_number, class_code)

            # 2. Increment Soft-Lock (G1.3.1.2)
            inventory.available_seats -= 1
            inventory.locked_until = datetime.utcnow() + timedelta(minutes=10) # 10m Standoff
            
            # 3. Create 'INTENT' Booking Record
            booking = self.booking_svc.create_booking(
                user_id=user_id,
                route_id=route_payload.get("route_id", "dynamic"),
                travel_date=travel_date,
                booking_details=route_payload,
                amount_paid=route_payload.get("fare", 0.0),
                passenger_details_list=route_payload.get("passenger_details", [])
            )
            booking.status = "PENDING_PAYMENT"
            booking.escrow_status = "INTENT_LOCK"
            
            inventory.locked_by_booking_id = booking.id
            self.db.commit()

            duration = time.perf_counter() - start_time
            self._metrics.histogram("hold_duration_seconds", duration)
            self._metrics.counter("hold_success_total", tags={"train": train_number, "class": class_code})
            logger.info(f"🛡️ [STANDOFF] Seat soft-locked for {user_id} on {train_number} for 10 minutes.")
            
            return {
                "status": "HOLD_SUCCESS",
                "booking_id": booking.id,
                "expires_at": inventory.locked_until.isoformat(),
                "message": "Seat reserved for 10 minutes while you complete payment."
            }

        except Exception as e:
            duration = time.perf_counter() - start_time
            self._metrics.histogram("hold_duration_seconds", duration)
            self._metrics.counter("hold_expired_total", tags={"error_type": type(e).__name__})
            logger.error(f"🚨 [STANDOFF] Hold Failure: {e}")
            self.db.rollback()
            return {"status": "FAILED", "reason": "HOLD_ERROR"}

    @track_metrics(service="booking_orchestrator", operation="execute_smart_booking")
    @_booking_circuit_breaker
    @_booking_retry_policy
    async def execute_smart_booking(self, user_id: str, route_payload: Optional[Dict] = None, passenger_details: Optional[List[Dict]] = None, booking_id: Optional[str] = None) -> Dict:
        """
        Orchestrates an end-to-end booking with JIT verification, predictive hold finalization, and Flex-Route Fallback.
        """
        start_time = time.perf_counter()
        # 1. Check for Existing Hold
        if booking_id:
            from database.models import Booking, SeatInventory, EscrowStatus
            booking = self.db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user_id).first()
            if booking and booking.status == "PENDING_PAYMENT":
                logger.info(f"🔄 [STANDOFF] Finalizing existing hold for Booking {booking_id}")
                
                # Check if hold expired
                inventory = self.db.query(SeatInventory).filter(SeatInventory.locked_by_booking_id == booking_id).first()
                if not inventory or (inventory.locked_until and inventory.locked_until < datetime.utcnow()):
                    return {"status": "FAILED", "reason": "HOLD_EXPIRED"}
                
                # Double-Verify with Source (G1.1.2)
                verif = await booking_verification_service.verify_availability(
                    booking.train_number, booking.source_code, booking.destination_code, 
                    booking.travel_date, booking.coach_type
                )
                if not verif.get("is_available"):
                    self.db.rollback()
                    return {"status": "FAILED", "reason": "PROVIDER_SOURCE_SOLD_OUT"}

                booking.status = "CONFIRMED"
                booking.escrow_status = "VERIFIED"
                inventory.locked_until = None # Perm-lock
                self.db.commit()
                
                duration = time.perf_counter() - start_time
                self._metrics.histogram("booking_duration_seconds", duration)
                self._metrics.counter("bookings_success", tags={"type": "finalize_hold"})
                return {"status": "SUCCESS", "booking_id": booking.id}

        # 2. Fresh Booking Flow
        if not route_payload:
            return {"status": "FAILED", "reason": "MISSING_PAYLOAD"}

        train_number = route_payload.get("train_number")
        source = route_payload.get("source")
        destination = route_payload.get("destination")
        travel_date = route_payload.get("travel_date")
        class_code = route_payload.get("class_code")
        
        # [G1.1.3] Queue-Warden Admission Control
        if not await queue_warden.acquire_checkout_slot(train_number, class_code):
            return {
                "status": "QUEUE_FULL",
                "message": "Too many concurrent checkouts for this train. Please retry in 15 seconds."
            }

        try:
            # [G1.1.1] Atomic Row-Lock for Concurrency Hardening
            from database.models import SeatInventory, Trip
            
            # 1. Acquire Atomic Lock on Inventory Branch
            trip = self.db.query(Trip).filter(Trip.trip_id == train_number).first()
            if not trip:
                logger.warning(f"⚠️ [ORCHESTRATOR] Trip ID not found for {train_number}")
                return {"status": "FAILED", "reason": "TRIP_NOT_FOUND"}

            try:
                # SELECT ... FOR UPDATE to hold this specific seat inventory row
                inventory = self.db.query(SeatInventory).filter(
                    SeatInventory.trip_id == trip.id,
                    SeatInventory.travel_date == travel_date,
                    SeatInventory.coach_type == class_code
                ).with_for_update().first()

                if not inventory or inventory.available_seats <= 0:
                    logger.warning(f"⚠️ [ORCHESTRATOR] Race Condition detected: {train_number} sold out mid-checkout.")
                    return await self._trigger_flex_fallback(source, destination, travel_date, train_number, class_code)

                # Reserve local seat count temporarily
                inventory.available_seats -= 1
                inventory.locked_until = datetime.utcnow() + timedelta(minutes=15)
                inventory.last_updated = datetime.utcnow()
                self.db.flush()

                logger.info(f"🔒 [ORCHESTRATOR] Atomic Lock acquired for Seat ID {inventory.id}.")

                # [G1.1.2] JIT 'Double-Verify' Signal (Provider Parity)
                jit_verif = await booking_verification_service.verify_availability(
                    train_number, source, destination, travel_date, class_code
                )
                if not jit_verif.get("is_available"):
                    logger.warning(f"⚠️ [ORCHESTRATOR] Provider Out-of-Sync: {train_number} sold out at source.")
                    inventory.available_seats += 1
                    self.db.rollback()
                    return await self._trigger_flex_fallback(source, destination, travel_date, train_number, class_code)
                
                logger.info("✅ [ORCHESTRATOR] JIT Verification passed. Proceeding to finalize.")

            except Exception as e:
                logger.error(f"🚨 [ORCHESTRATOR] Concurrency/JIT Failure: {e}")
                self.db.rollback()
                return {"status": "FAILED", "reason": "LOCK_OR_JIT_ERROR"}

            # 3. Proceed with Booking creation
            booking = self.booking_svc.create_booking(
                user_id=user_id,
                route_id=route_payload.get("route_id", "dynamic"),
                travel_date=travel_date,
                booking_details=route_payload,
                amount_paid=route_payload.get("fare", 0.0),
                passenger_details_list=passenger_details or []
            )
            self.db.commit()
            
            duration = time.perf_counter() - start_time
            self._metrics.histogram("booking_duration_seconds", duration)
            self._metrics.counter("bookings_success", tags={"type": "fresh_booking", "train": train_number})
            return {"status": "SUCCESS", "booking_id": booking.id}

        except Exception as e:
            duration = time.perf_counter() - start_time
            self._metrics.histogram("booking_duration_seconds", duration)
            self._metrics.counter("bookings_failed", tags={"error_type": type(e).__name__})
            raise
        finally:
            # [G1.1.3] Release Semaphore Slot
            await queue_warden.release_checkout_slot(train_number, class_code)

    @_flex_fallback_circuit_breaker
    async def _trigger_flex_fallback(self, source, destination, travel_date, train_number, class_code):
        """Helper to invoke Flex-Route Agent fallback."""
        self._metrics.counter("flex_fallbacks_total", tags={"train": train_number, "class": class_code})
        alt_results = await flex_route_agent.find_alternatives(
            source, destination, travel_date, original_train=train_number, original_class=class_code
        )
        if alt_results:
            return {
                "status": "FLEX_OFFERED",
                "reason": "ORIGINAL_SOLD_OUT",
                "alternatives": alt_results,
                "message": "Seat sold out. Our AI found these alternatives."
            }
        return {"status": "FAILED", "reason": "SOLD_OUT_NO_ALT"}

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "booking_orchestrator",
            "booking_circuit_breaker_state": self._booking_circuit_breaker.state.name,
            "booking_circuit_breaker_failures": self._booking_circuit_breaker.failure_count,
            "flex_fallback_circuit_breaker_state": self._flex_fallback_circuit_breaker.state.name,
            "flex_fallback_circuit_breaker_failures": self._flex_fallback_circuit_breaker.failure_count,
            "bookings_total": self._metrics.get_counter("bookings_total"),
            "bookings_success": self._metrics.get_counter("bookings_success"),
            "bookings_failed": self._metrics.get_counter("bookings_failed"),
            "flex_fallbacks_total": self._metrics.get_counter("flex_fallbacks_total"),
            "hold_success_total": self._metrics.get_counter("hold_success_total"),
            "hold_expired_total": self._metrics.get_counter("hold_expired_total"),
            "booking_duration_p50": self._metrics.get_percentile("booking_duration_seconds", 50),
            "booking_duration_p95": self._metrics.get_percentile("booking_duration_seconds", 95),
            "hold_duration_p50": self._metrics.get_percentile("hold_duration_seconds", 50),
            "hold_duration_p95": self._metrics.get_percentile("hold_duration_seconds", 95),
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if (self._booking_circuit_breaker.state == CircuitState.CLOSED and 
                                   self._flex_fallback_circuit_breaker.state == CircuitState.CLOSED) else "degraded",
            "service": "booking_orchestrator",
            "booking_circuit_breaker": self._booking_circuit_breaker.state.name,
            "flex_fallback_circuit_breaker": self._flex_fallback_circuit_breaker.state.name,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self, breaker_name: str = "all"):
        """Reset circuit breaker(s) to closed state."""
        if breaker_name == "all" or breaker_name == "booking":
            self._booking_circuit_breaker.reset()
        if breaker_name == "all" or breaker_name == "flex_fallback":
            self._flex_fallback_circuit_breaker.reset()
        logger.info(f"🔄 [ORCHESTRATOR] Circuit breaker '{breaker_name}' reset")

# Factory function for convenience in FastAPI dependencies
def get_booking_orchestrator(db: Session = None):
    # In practice, db would be provided by a dependency
    return BookingOrchestrator(db)
