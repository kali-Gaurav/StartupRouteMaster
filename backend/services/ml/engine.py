import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.system_monitor import system_monitor, SystemState
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("routemaster.ml_service")

class MLMicroservice:
    """
    Task 7: Decoupled ML Microservice Engine.
    Handles Predictive Modeling (Delays, Cancellation, Demand) with Load-Aware Shedding.
    """
    # [G19.5] ML Resilience Layer: Class-level decorators for scoping
    _delay_prediction_circuit_breaker = circuit_breaker(
        name="ml_delay_prediction",
        failure_threshold=5,
        recovery_timeout=60.0
    )
    _reliability_prediction_circuit_breaker = circuit_breaker(
        name="ml_reliability_prediction",
        failure_threshold=5,
        recovery_timeout=60.0
    )
    _tatkal_demand_circuit_breaker = circuit_breaker(
        name="ml_tatkal_demand",
        failure_threshold=3,
        recovery_timeout=120.0
    )
    _ml_retry_policy = retry_policy(
        max_attempts=2,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        base_delay=0.5,
        max_delay=5.0
    )

    def __init__(self, db_session):
        self.db = db_session
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name="ml_microservice",
            default_tags={"component": "ml"}
        )
        self._metrics.gauge("delay_prediction_circuit_breaker_state", lambda: self._delay_prediction_circuit_breaker.state.value)
        self._metrics.gauge("reliability_prediction_circuit_breaker_state", lambda: self._reliability_prediction_circuit_breaker.state.value)
        self._metrics.gauge("tatkal_demand_circuit_breaker_state", lambda: self._tatkal_demand_circuit_breaker.state.value)
        self._metrics.counter("predictions_total")
        self._metrics.counter("predictions_success")
        self._metrics.counter("predictions_failed")
        self._metrics.counter("predictions_skipped_total")
        self._metrics.histogram("prediction_duration_seconds")
        self._metrics.histogram("prediction_latency_ms")
        
    async def predict_delay(self, train_number: str, station_code: str) -> Dict[str, Any]:
        """Latency-sensitive delay prediction with propagation awareness."""
        start_time = time.perf_counter()
        state = system_monitor.current_state
        if state >= SystemState.CRITICAL:
            self._metrics.counter("predictions_skipped_total", tags={"reason": "system_overload", "type": "delay"})
            return {"status": "skipped", "reason": "system_overload", "predicted_delay_mins": 0}

        from services.ml.delayed_models import DelayPredictionModel
        # [Task 14.2] Real-time delay propagation
        predictor = DelayPredictionModel()
        
        try:
            # In a real scenario, we'd fetch the current delay from RealtimeOverlay
            # and predict the 'target station' delay.
            prediction = predictor.predict(self.db, train_number, 0, 0) # Placeholder indices
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            self._metrics.histogram("prediction_latency_ms", duration_ms)
            self._metrics.counter("predictions_success", tags={"type": "delay"})
            return {
                "status": "success",
                "predicted_delay_mins": prediction or 0,
                "ml_latency_ms": duration_ms
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.histogram("prediction_latency_ms", duration_ms)
            self._metrics.counter("predictions_failed", tags={"type": "delay", "error_type": type(e).__name__})
            raise

    @track_metrics(service="ml_microservice", operation="get_route_reliability")
    @_reliability_prediction_circuit_breaker
    @_ml_retry_policy
    async def get_route_reliability(self, route: Any) -> float:
        """
        🛡️ TASK 14.1/14.3: Integrated ML-based reliability predictions.
        Combines trip reliability and transfer success confidence.
        """
        from services.ml.reliability_model import get_reliability_model
        model = await get_reliability_model()
        
        total_confidence = 1.0
        
        # 1. Score each segment
        for segment in getattr(route, 'segments', []):
            conf = await model.predict(
                trip_id=segment.trip_id,
                origin_stop_id=segment.departure_stop_id,
                destination_stop_id=segment.arrival_stop_id,
                departure_time=segment.departure_time,
                distance_km=segment.distance_km
            )
            total_confidence *= conf
            
        # 2. Score each transfer [Task 14.3]
        from services.ml.delayed_models import TransferSuccessProbabilityModel
        transfer_model = TransferSuccessProbabilityModel()
        for tr in getattr(route, 'transfers', []):
            # Probability of making the transfer given historical delay variance
            prob = transfer_model.get_transfer_success_probability(
                arrival_delay=0, # Assume on-time for baseline reliability
                transfer_buffer_minutes=tr.duration_minutes
            )
            total_confidence *= prob
            
        return round(total_confidence, 4)

    async def predict_tatkal_demand(self, train_number: str, travel_date: str) -> Dict[str, Any]:
        """Heavy ML Task for Tatkal Demand."""
        state = system_monitor.current_state
        if state >= SystemState.WARNING:
            # Skip heavy Tatkal ML during WARNING to save RAM/CPU
            return {"status": "skipped", "demand_index": 0.5}

        from services.tatkal_demand_predictor import TatkalDemandPredictor
        predictor = TatkalDemandPredictor(self.db)
        
        return await predictor.predict_demand(train_number, travel_date)
