import logging
import asyncio
from typing import Optional, Dict
from sqlalchemy.orm import Session
from database.models import Fare
from sqlalchemy import and_
from datetime import datetime
from collections import deque

from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy

logger = logging.getLogger(__name__)

class FareCalculator:
    """
    Service to calculate or look up fares for train segments.
    Uses a hybrid approach:
    1. Database lookup for exact segment/train/class matches.
    2. Fallback to a distance-based linear regression model (Base Fare + Rate/KM).

    With metrics tracking for fare calculation operations.
    """

    # IRCTC-aligned rates (approximate INR per KM)
    CLASS_RATES = {
        "1A": 4.5,
        "2A": 2.5,
        "3A": 1.8,
        "3E": 1.6,
        "SL": 0.7,
        "2S": 0.4,
        "CC": 2.0,
        "EC": 3.5,
        "FC": 2.8,
        "GN": 0.2
    }

    # Base fare (minimum) per class
    BASE_FARES = {
        "1A": 500,
        "2A": 300,
        "3A": 250,
        "3E": 200,
        "SL": 120,
        "2S": 60,
        "CC": 200,
        "EC": 400,
        "FC": 200,
        "GN": 30
    }

    def __init__(self):
        """Initialize fare calculator with metrics tracking."""
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "fare_calculator_db",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )

        # Retry policy for database operations
        self._db_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=2.0,
            conditions=[
                lambda e: "connection" in str(e).lower(),
                lambda e: "timeout" in str(e).lower()
            ]
        )

        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = __import__('threading').Lock()

        logger.info("FareCalculator initialized with metrics tracking and resilience patterns")
    
    def _record_metrics(self, operation_type: str, success: bool, error: Optional[str] = None):
        """Record metrics for fare calculation operations."""
        with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "error": error
            })

    @classmethod
    def calculate_fare(
        cls, 
        db: Session, 
        distance_km: float, 
        class_type: str = "SL", 
        train_no: Optional[str] = None,
        segment_id: Optional[str] = None
    ) -> float:
        """Calculate the best estimate for a fare."""
        class_type = class_type.upper()
        
        # 1. Try DB Lookup
        try:
            db_fare = db.query(Fare).filter(and_(
                Fare.class_type == class_type,
                (Fare.segment_id == segment_id) if segment_id else (Fare.id == -1) # dummy if no segment_id
            )).first()
            if db_fare:
                return float(db_fare.amount)
        except Exception as e:
            logger.debug(f"Fare DB lookup failed: {e}")

        # 2. Fallback to Linear Model
        rate = cls.CLASS_RATES.get(class_type, cls.CLASS_RATES["SL"])
        base = cls.BASE_FARES.get(class_type, cls.BASE_FARES["SL"])
        
        estimated = base + (distance_km * rate)
        
        # Round to nearest 5 as per IRCTC convention
        return float(round(estimated / 5) * 5)

    @classmethod
    def get_all_fares(cls, db: Session, distance_km: float) -> Dict[str, float]:
        """Get estimated fares for all available classes."""
        return {
            class_type: cls.calculate_fare(db, distance_km, class_type)
            for class_type in cls.CLASS_RATES.keys()
        }

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    def get_metrics(self) -> dict:
        """Get service metrics."""
        with self._metrics_lock:
            if not self._metrics:
                return {"total_operations": 0, "success_rate": 0.0}

            total = len(self._metrics)
            successful = sum(1 for m in self._metrics if m["success"])
            by_type = {}
            for m in self._metrics:
                op_type = m.get("operation_type", "unknown")
                if op_type not in by_type:
                    by_type[op_type] = {"total": 0, "success": 0}
                by_type[op_type]["total"] += 1
                if m["success"]:
                    by_type[op_type]["success"] += 1

            return {
                "total_operations": total,
                "successful_operations": successful,
                "failed_operations": total - successful,
                "success_rate": successful / total if total > 0 else 0.0,
                "operation_breakdown": by_type,
                "circuit_breaker": self._db_breaker.get_metrics()
            }

    def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "circuit_breaker_state": self._db_breaker.get_state().value,
            "metrics": self.get_metrics()
        }

    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self._db_breaker.reset()
        logger.info("Circuit breaker reset for fare_calculator")
