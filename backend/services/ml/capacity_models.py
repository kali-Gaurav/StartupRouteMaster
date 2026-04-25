"""
Capacity Prediction Models for RouteMaster V2.
Predicts seat availability probability and occupancy trends.
"""

import logging
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database.models import SeatAvailability, TrainMaster
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger(__name__)

class CapacityPredictionModel:
    """
    Predicts the probability of a seat being available for a given train/date/class.
    Uses historical availability logs (The Moat Dataset).
    """
    
    # [G19.5] ML Resilience Layer: Class-level decorators for scoping
    _prediction_circuit_breaker = circuit_breaker(
        name="capacity_prediction",
        failure_threshold=5,
        recovery_timeout=60.0
    )
    _prediction_retry_policy = retry_policy(
        max_attempts=3,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        base_delay=0.5,
        max_delay=10.0
    )

    def __init__(self):
        self.is_trained = False
        # Placeholder for actual model (XGBoost/RandomForest)
        self.model = None
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name="capacity_prediction_model",
            default_tags={"component": "ml"}
        )
        self._metrics.gauge("circuit_breaker_state", lambda: self._prediction_circuit_breaker.state.value)
        self._metrics.counter("predictions_total")
        self._metrics.counter("predictions_success")
        self._metrics.counter("predictions_failed")
        self._metrics.histogram("prediction_duration_seconds") 

    @track_metrics(service="capacity_prediction_model", operation="predict_availability_probability")
    @_prediction_circuit_breaker
    @_prediction_retry_policy
    def predict_availability_probability(self, session: Session, train_number: str, 
                                        class_code: str, travel_date: datetime, 
                                        quota: str = "GN") -> float:
        """
        Returns P(Available) - probability from 0.0 to 1.0.
        
        Logic for 0-Data Start:
        1. If no historical data, return a baseline based on train type.
        2. If historical data exists, use trend analysis.
        """
        try:
            # Normalize travel_date to date for database consistency
            if isinstance(travel_date, datetime):
                travel_date_norm = travel_date.date()
            else:
                travel_date_norm = travel_date

            # 1. Fetch recent history for this specific combination
            history = session.query(SeatAvailability).filter(
                SeatAvailability.train_number == train_number,
                SeatAvailability.class_code == class_code,
                SeatAvailability.quota == quota,
                func.date(SeatAvailability.travel_date) == travel_date_norm
            ).order_by(desc(SeatAvailability.check_date)).limit(10).all()
            
            if not history:
                return self._get_baseline_probability(session, train_number, class_code)
                
            # 2. Simple Heuristic if model not yet trained:
            # Check latest status
            latest = history[0]
            status = latest.availability_status.upper()
            
            if "AVAILABLE" in status or "CURR_AVBL" in status:
                # If available now, probability is high but decays as travel_date nears
                days_left = (travel_date - datetime.utcnow()).days
                return max(0.6, 1.0 - (0.01 * (30 - max(0, days_left))))
                
            if "WL" in status:
                # If in Waiting List, probability depends on WL number
                wl_num = latest.waiting_list_number or 100
                if wl_num < 10: return 0.5
                if wl_num < 50: return 0.2
                return 0.05
                
            return 0.5 # Default neutral
            
        except Exception as e:
            logger.error(f"Error predicting availability for {train_number}: {e}")
            return 0.5

    def _get_baseline_probability(self, session: Session, train_number: str, class_code: str) -> float:
        """Baseline P(avail) based on train frequency and type."""
        train = session.query(TrainMaster).filter(TrainMaster.train_number == train_number).first()
        if not train: return 0.5
        
        # Express trains usually have lower availability than local/fast passengers
        if "Express" in (train.type or ""):
            return 0.4 if class_code in ["3A", "SL"] else 0.6
        return 0.7

    def get_occupancy_penalty(self, probability: float) -> float:
        """
        Calculates a penalty score for the routing engine.
        Low probability (high occupancy) -> High penalty.
        """
        # Penalty = (1 - P)^2 * 100 
        # Example: P=1.0 -> 0 penalty. P=0.0 -> 100 penalty.
        return round(((1.0 - probability) ** 2) * 100, 2)

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "capacity_prediction_model",
            "circuit_breaker_state": self._prediction_circuit_breaker.state.name,
            "circuit_breaker_failures": self._prediction_circuit_breaker.failure_count,
            "predictions_total": self._metrics.get_counter("predictions_total"),
            "predictions_success": self._metrics.get_counter("predictions_success"),
            "predictions_failed": self._metrics.get_counter("predictions_failed"),
            "prediction_duration_p50": self._metrics.get_percentile("prediction_duration_seconds", 50),
            "prediction_duration_p95": self._metrics.get_percentile("prediction_duration_seconds", 95),
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if self._prediction_circuit_breaker.state == CircuitState.CLOSED else "degraded",
            "service": "capacity_prediction_model",
            "circuit_breaker": self._prediction_circuit_breaker.state.name,
            "is_trained": self.is_trained,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker to closed state."""
        self._prediction_circuit_breaker.reset()
        logger.info("🔄 [CAPACITY] Circuit breaker reset for capacity prediction")
