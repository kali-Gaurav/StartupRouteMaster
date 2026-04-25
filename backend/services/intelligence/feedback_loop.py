import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from database.models import RouteSearchLog, Booking, SearchAccuracyMetric
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("intelligence.feedback")

class AccuracyFeedbackLoop:
    """
    [Group 4] Closed-Loop Feedback Loop.
    Reconciles predicted availability results with actual booking outcomes.
    """
    def __init__(self, db: Session):
        self.db = db
        # Circuit breaker for feedback reconciliation
        self._reconciliation_circuit_breaker = circuit_breaker(
            name="feedback_reconciliation",
            failure_threshold=5,
            recovery_timeout=60.0
        )
        # Retry policy
        self._reconciliation_retry_policy = retry_policy(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=0.5,
            max_delay=10.0
        )
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name="accuracy_feedback_loop",
            default_tags={"component": "intelligence"}
        )
        self._metrics.gauge("reconciliation_circuit_breaker_state", lambda: self._reconciliation_circuit_breaker.state.value)
        self._metrics.counter("reconciliations_total")
        self._metrics.counter("reconciliations_success")
        self._metrics.counter("reconciliations_failed")
        self._metrics.counter("search_outcomes_total")
        self._metrics.counter("search_outcomes_match")
        self._metrics.counter("search_outcomes_mismatch")
        self._metrics.histogram("reconciliation_duration_seconds")

    @track_metrics(service="accuracy_feedback_loop", operation="reconcile_search_outcomes")
    @_reconciliation_circuit_breaker
    @_reconciliation_retry_policy
    async def reconcile_search_outcomes(self, lookback_hours: int = 12) -> int:
        """
        Scans bookings from the last N hours and compares them with the search logs that preceded them.
        """
        start_time = time.perf_counter()
        threshold_time = datetime.utcnow() - timedelta(hours=lookback_hours)
        
        # 1. Fetch recent bookings
        bookings = self.db.query(Booking).filter(
            Booking.created_at >= threshold_time
        ).all()

        reconciled_count = 0
        for booking in bookings:
            # 2. Find the search log for this user/route just before booking
            search_log = self.db.query(RouteSearchLog).filter(
                RouteSearchLog.user_id == booking.user_id,
                RouteSearchLog.src == (booking.boarding_station or ""),
                RouteSearchLog.dst == (booking.destination_station or ""),
                RouteSearchLog.created_at <= booking.created_at
            ).order_by(RouteSearchLog.created_at.desc()).first()

            if search_log:
                # 3. Create Accuracy Metric
                # Note: In a real system, SearchLog would store the 'predicted_status'
                is_match = booking.status == "SUCCESS"
                metric = SearchAccuracyMetric(
                    search_id=search_log.id,
                    train_number=booking.train_number,
                    predicted_status="AVAILABLE", # Assuming search showed it as bookable
                    actual_status="CONFIRMED" if booking.status == "SUCCESS" else "FAILED",
                    is_match=is_match
                )
                self.db.add(metric)
                reconciled_count += 1
                self._metrics.counter("search_outcomes_total", tags={"match": str(is_match)})
        
        self.db.commit()
        
        duration = time.perf_counter() - start_time
        self._metrics.histogram("reconciliation_duration_seconds", duration)
        self._metrics.counter("reconciliations_success", tags={"lookback_hours": str(lookback_hours)})
        logger.info(f"🔄 [FEEDBACK] Reconciled {reconciled_count} search outcomes against actual bookings in {duration:.3f}s")
        return reconciled_count

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "accuracy_feedback_loop",
            "circuit_breaker_state": self._reconciliation_circuit_breaker.state.name,
            "circuit_breaker_failures": self._reconciliation_circuit_breaker.failure_count,
            "reconciliations_total": self._metrics.get_counter("reconciliations_total"),
            "reconciliations_success": self._metrics.get_counter("reconciliations_success"),
            "reconciliations_failed": self._metrics.get_counter("reconciliations_failed"),
            "search_outcomes_total": self._metrics.get_counter("search_outcomes_total"),
            "search_outcomes_match": self._metrics.get_counter("search_outcomes_match"),
            "search_outcomes_mismatch": self._metrics.get_counter("search_outcomes_mismatch"),
            "reconciliation_duration_p50": self._metrics.get_percentile("reconciliation_duration_seconds", 50),
            "reconciliation_duration_p95": self._metrics.get_percentile("reconciliation_duration_seconds", 95),
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if self._reconciliation_circuit_breaker.state == CircuitState.CLOSED else "degraded",
            "service": "accuracy_feedback_loop",
            "circuit_breaker": self._reconciliation_circuit_breaker.state.name,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker to closed state."""
        self._reconciliation_circuit_breaker.reset()
        logger.info("🔄 [FEEDBACK] Circuit breaker reset for feedback reconciliation")

def get_feedback_loop(db: Session):
    return AccuracyFeedbackLoop(db)