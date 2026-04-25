import logging
import asyncio
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from database.models import BookingRequest, BookingRequestPassenger, BookingQueue, User
from services.telegram_service import send_telegram_message, format_booking_alert
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import retry_async, RetryPolicy
from collections import deque

logger = logging.getLogger(__name__)

class BookingQueueService:
    """
    Service for managing booking queue with resilience patterns.
    """
    
    def __init__(self, db: Session):
        self.db = db
        
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "booking_queue_db",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0)
        )
        
        # Circuit breaker for telegram notifications
        self._telegram_breaker = circuit_breaker_manager.get_or_create(
            "booking_queue_telegram",
            CircuitConfig(failure_threshold=3, timeout_seconds=30.0)
        )
        
        # Retry policy
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("BookingQueueService initialized with resilience patterns")

    async def create_request(
        self,
        user_id: str,
        journey_data: Dict[str, Any],
        passengers: List[Dict[str, Any]],
        phone: str,
        email: str
    ) -> BookingRequest:
        """
        Creates a new booking request and adds it to the manual execution queue.
        Triggers a Telegram alert for the admin.
        """
        # 1. Create the BookingRequest
        new_request = BookingRequest(
            user_id=user_id,
            source_station=journey_data.get("source", "Unknown"),
            destination_station=journey_data.get("destination", "Unknown"),
            journey_date=datetime.strptime(journey_data.get("date", str(date.today())), "%Y-%m-%d").date(),
            train_number=journey_data.get("legs", [{}])[0].get("train_number", "00000"),
            train_name=journey_data.get("legs", [{}])[0].get("train_name", "Unknown"),
            class_type=journey_data.get("preferred_class", "AC_THREE_TIER"),
            status="PENDING",
            route_details=journey_data
        )
        self.db.add(new_request)
        self.db.flush()

        # 2. Add Passengers
        for p in passengers:
            pax = BookingRequestPassenger(
                booking_request_id=new_request.id,
                name=p.get("name"),
                age=p.get("age"),
                gender=p.get("gender"),
                berth_preference=p.get("preference")
            )
            self.db.add(pax)

        # 3. Add to Queue
        queue_entry = BookingQueue(
            booking_request_id=new_request.id,
            priority=5,
            status="WAITING"
        )
        self.db.add(queue_entry)
        
        self.db.commit()
        self.db.refresh(new_request)

        # 4. Trigger Telegram Alert
        try:
            alert_msg = format_booking_alert(
                booking_id=str(new_request.id),
                journey=journey_data,
                passengers=passengers,
                phone=phone,
                email=email
            )
            await send_telegram_message(alert_msg)
        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")

        return new_request

    def get_pending_queue(self) -> List[BookingQueue]:
        return self.db.query(BookingQueue).filter(BookingQueue.status == "WAITING").all()

    async def update_status(self, request_id: str, status: str, admin_id: str, notes: str = None):
        """
        Updates the status of a booking request (e.g., SUCCESS, FAILED).
        This is called by the admin manually.
        """
        request = self.db.query(BookingRequest).filter(BookingRequest.id == request_id).first()
        if not request:
            return None
            
        request.status = status
        
        queue_entry = self.db.query(BookingQueue).filter(BookingQueue.booking_request_id == request_id).first()
        if queue_entry:
            queue_entry.status = "DONE" if status == "SUCCESS" else "FAILED"
            queue_entry.executed_by = admin_id
            queue_entry.execution_notes = notes
            queue_entry.completed_at = datetime.utcnow()
            
        self.db.commit()
        return request

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(self, action: str, success: bool):
        """Record queue operation metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "action": action,
                "success": success
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_action = {}
        for m in self._metrics:
            action = m["action"]
            by_action[action] = by_action.get(action, 0) + 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_action,
            "circuit_breaker_states": {
                "db": self._db_breaker.get_state().value,
                "telegram": self._telegram_breaker.get_state().value
            }
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breakers": {
                "db": self._db_breaker.get_state().value,
                "telegram": self._telegram_breaker.get_state().value
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self._db_breaker.reset()
        self._telegram_breaker.reset()
        logger.info("All circuit breakers reset for booking queue service")
