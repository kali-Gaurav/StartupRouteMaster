import logging
from typing import Dict, Any, Optional
from datetime import datetime
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger(__name__)

class AvailabilityHeuristic:
    """
    Task 15: ML Availability Heuristic Edge Scoring.
    Estimates confirmation probability without hitting external APIs.
    """
    
    # Circuit breaker for heuristic calculations (Class-level for decorator use)
    _heuristic_circuit_breaker = circuit_breaker(
        name="availability_heuristic",
        failure_threshold=10,
        recovery_timeout=30.0
    )
    
    def __init__(self):
        # In production, this would load a real .pkl model
        pass
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name="availability_heuristic",
            default_tags={"component": "ml"}
        )
        self._metrics.gauge("circuit_breaker_state", lambda: 0) # Mocked
        self._metrics.counter("calculations_total")
        self._metrics.counter("calculations_success")
        self._metrics.counter("calculations_failed")
        self._metrics.histogram("calculation_duration_seconds")

    def _get_peak_season_weight(self, d: datetime) -> float:
        """[Task 16.5] Indian Festivals & Peak Seasons Weighting."""
        # 1. Summer Vacation (May-June)
        if d.month in [5, 6]: return -0.15
        # 2. Diwali/Dussehra Window (Oct-Nov varies, approximating)
        if d.month in [10, 11]: return -0.20
        # 3. Holi (March)
        if d.month == 3: return -0.10
        # 4. Christmas/New Year Rush
        if d.month == 12 and d.day >= 20: return -0.15
        return 0.0

    @track_metrics(service="availability_heuristic", operation="estimate_confirmation_chance")
    @_heuristic_circuit_breaker
    def estimate_confirmation_chance(self, train_no: str, class_type: str, travel_date: datetime, quota: str = "GN") -> float:
        """
        [16.1] Fine-tuned confirmation probability model.
        [16.2] Proximity-based decay (Booking window factor).
        """
        prob = 0.65 
        
        # 1. Class Factor (Subtask 16.3)
        # 1A=FirstAC, 2A=SecondAC, 3A=ThirdAC, 3E=ThirdEconomy, SL=Sleeper, CC=ChairCar, EV=Vistadome
        class_map = {
            "1A": 0.25, "2A": 0.18, "3A": 0.08, "3E": 0.04, 
            "SL": -0.25, "CC": 0.12, "2S": -0.35, "EV": 0.20, "FC": 0.15
        }
        prob += class_map.get(class_type.upper(), 0.0)
        
        # 2. Quota Factor [Task 16.6]
        quota_map = {"GN": 0.0, "TQ": -0.15, "PT": -0.10, "LD": 0.25, "DF": 0.30}
        prob += quota_map.get(quota.upper(), 0.0)

        # 3. Proximity Factor (Subtask 16.2)
        days_diff = (travel_date.date() - datetime.now().date()).days
        if days_diff > 60:
            prob += 0.15 
        elif days_diff < 7:
            prob -= 0.20 
        elif days_diff < 2:
            prob -= 0.40 
            
        # 4. Seasonal & Weekend Weights
        prob += self._get_peak_season_weight(travel_date)
        if travel_date.weekday() in [4, 5, 6]: # Fri-Sun
            prob -= 0.1
            
        # 5. Elite Train Priority (Rajdhani/Shatabdi usually have higher clearance)
        if str(train_no).startswith(('124', '120', '224')):
            prob += 0.05
        # Known congested routes penalty
        elif str(train_no) in ["12626", "12121", "12424"]:
            prob -= 0.15
            
        return max(0.02, min(0.99, prob))

    def get_route_availability_score(self, segments: list) -> float:
        """
        Calculates aggregate availability for a multi-leg route.
        [16.4] Multi-leg Complexity Penalty.
        """
        if not segments: return 1.0
        
        total_prob = 1.0
        for s in segments:
            # Try to extract metadata
            cls = s.metadata.get("class_type", "3A") if hasattr(s, 'metadata') else "3A"
            q = s.metadata.get("quota", "GN") if hasattr(s, 'metadata') else "GN"
            total_prob *= self.estimate_confirmation_chance(s.train_number, cls, s.departure_time, q)
            
        # [16.4] Complexity Penalty: 10% reduction for each transfer
        if len(segments) > 1:
            penalty = (len(segments) - 1) * 0.1
            total_prob *= (1.0 - penalty)
            
        return max(0.01, round(total_prob, 4))

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "availability_heuristic",
            "circuit_breaker_state": self._heuristic_circuit_breaker.state.name,
            "circuit_breaker_failures": self._heuristic_circuit_breaker.failure_count,
            "calculations_total": self._metrics.get_counter("calculations_total"),
            "calculations_success": self._metrics.get_counter("calculations_success"),
            "calculations_failed": self._metrics.get_counter("calculations_failed"),
            "calculation_duration_p50": self._metrics.get_percentile("calculation_duration_seconds", 50),
            "calculation_duration_p95": self._metrics.get_percentile("calculation_duration_seconds", 95),
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if self._heuristic_circuit_breaker.state == CircuitState.CLOSED else "degraded",
            "service": "availability_heuristic",
            "circuit_breaker": self._heuristic_circuit_breaker.state.name,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker to closed state."""
        self._heuristic_circuit_breaker.reset()
        logger.info("🔄 [HEURISTIC] Circuit breaker reset for availability heuristic")

availability_heuristic = AvailabilityHeuristic()
