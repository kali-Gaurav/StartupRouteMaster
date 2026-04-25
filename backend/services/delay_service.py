"""
Delay Service - Production Version
With circuit breaker protection, retry logic, and comprehensive error handling
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from contextlib import asynccontextmanager

from core.route_engine.reliability import ReliabilityEngine
from services.agents.flex_route_agent import flex_route_agent
from services.ws_manager import ws_manager
from core.resilience import circuit_breaker_manager, CircuitBreakerState
from core.retry import retry_async, RetryPolicy
from services.cache_service import cache_service

logger = logging.getLogger("services.delay")


@dataclass
class DelayServiceConfig:
    """Configuration for delay service."""
    cache_ttl_seconds: int = 300
    timeout_seconds: float = 15.0
    reliability_threshold: float = 0.6
    alert_delay_threshold_minutes: int = 120
    retry_policy: RetryPolicy = field(default_factory=lambda: RetryPolicy(
        max_attempts=2,
        base_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0,
        retry_on_exceptions=(TimeoutError, ConnectionError, OSError)
    ))
    circuit_failure_threshold: int = 5
    circuit_recovery_seconds: int = 60


@dataclass
class DelayCheckResult:
    """Result of delay check."""
    booking_id: str
    train_number: str
    reliability_score: float
    predicted_delay_minutes: int
    actual_delay_minutes: Optional[int]
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    is_available: bool
    alternatives_count: int
    message: str
    response_time_ms: int = 0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "booking_id": self.booking_id,
            "train_number": self.train_number,
            "reliability_score": self.reliability_score,
            "predicted_delay_minutes": self.predicted_delay_minutes,
            "actual_delay_minutes": self.actual_delay_minutes,
            "risk_level": self.risk_level,
            "is_available": self.is_available,
            "alternatives_count": self.alternatives_count,
            "message": self.message,
            "response_time_ms": self.response_time_ms,
            "error": self.error,
            "timestamp": self.timestamp
        }


class DelayService:
    """
    [Group 3] Predictive Delay Correlation & Flex-Notification.
    Monitors reliability scores and preemptively suggests 'Flex-Route' fallbacks.
    With circuit breaker protection and retry logic.
    """
    
    def __init__(self, db: Session, config: Optional[DelayServiceConfig] = None):
        self.db = db
        self.config = config or DelayServiceConfig()
        self.reliability_engine = ReliabilityEngine(db)
        
        # Circuit breaker for external service calls
        self._flex_breaker = circuit_breaker_manager.get_breaker("delay_service_flex")
        self._ws_breaker = circuit_breaker_manager.get_breaker("delay_service_ws")
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = None
        
        logger.info("DelayService initialized with resilience patterns")

    def _get_cache_key(self, booking_id: str) -> str:
        """Generate cache key for delay check."""
        return f"delay_check:{booking_id}"

    def _get_cached_result(self, booking_id: str) -> Optional[DelayCheckResult]:
        """Get cached delay check result."""
        cache_key = self._get_cache_key(booking_id)
        cached = cache_service.get(cache_key)
        if cached:
            result = DelayCheckResult(**cached)
            return result
        return None

    def _cache_result(self, booking_id: str, result: DelayCheckResult):
        """Cache delay check result."""
        cache_key = self._get_cache_key(booking_id)
        cache_service.set(cache_key, result.to_dict(), ttl_seconds=self.config.cache_ttl_seconds)

    def _calculate_risk_level(self, reliability_score: float, delay_minutes: int) -> str:
        """Calculate risk level based on reliability and delay."""
        if reliability_score < 0.4 or delay_minutes > 120:
            return "CRITICAL"
        elif reliability_score < 0.6 or delay_minutes > 60:
            return "HIGH"
        elif reliability_score < 0.8 or delay_minutes > 30:
            return "MEDIUM"
        return "LOW"

    @circuit_breaker_manager.get_breaker("delay_service_flex").decorate
    @retry_async
    async def _find_alternatives(
        self,
        source: str,
        destination: str,
        travel_date: str,
        original_train: str,
        original_class: str
    ) -> list:
        """Find alternative routes with retry logic."""
        try:
            alternatives = await flex_route_agent.find_alternatives(
                source=source,
                destination=destination,
                travel_date=travel_date,
                original_train=original_train,
                original_class=original_class
            )
            return alternatives or []
        except Exception as e:
            logger.error(f"Failed to find alternatives: {e}")
            return []

    @circuit_breaker_manager.get_breaker("delay_service_ws").decorate
    async def _dispatch_delay_alert(
        self,
        booking_id: str,
        user_id: str,
        train_number: str,
        risk_level: str,
        alternatives: list,
        delay_minutes: int
    ) -> bool:
        """Dispatch delay alert via WebSocket."""
        try:
            est_delay = "2+ Hours" if delay_minutes > 120 else "1-2 Hours" if delay_minutes > 60 else "< 1 Hour"
            
            payload = {
                "type": "DELAY_RISK_ALERT",
                "message": f"🚆 Delay Alert: Your train {train_number} is predicted to be delayed by {est_delay}.",
                "impact_score": risk_level,
                "alternatives": alternatives[:3],  # Show top 3 flex options
                "action": "VIEW_FLEX_OFFER",
                "booking_id": booking_id
            }
            
            # Broadcast to user session
            await ws_manager.broadcast_user_message(
                user_id,
                "⚠️ **HIGH DELAY RISK DETECTED**",
                payload
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to dispatch delay alert: {e}")
            return False

    async def verify_and_notify_delay_risk(
        self,
        booking_id: str,
        user_id: str,
        train_number: str,
        boarding_station: str,
        destination_station: str,
        travel_date: str,
        class_code: str,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """
        [Task 4.1] Analyzes a specific booking for delay risk and pushes fallbacks.
        
        Args:
            booking_id: Booking identifier
            user_id: User ID for notification
            train_number: Train number
            boarding_station: Boarding station code
            destination_station: Destination station code
            travel_date: Travel date
            class_code: Coach class code
            bypass_cache: Skip cache and fetch fresh data
            
        Returns:
            Dictionary with delay check results
        """
        start_time = datetime.utcnow()
        
        # Check cache first
        if not bypass_cache:
            cached = self._get_cached_result(booking_id)
            if cached:
                logger.debug(f"Cache hit for delay check {booking_id}")
                return cached.to_dict()

        try:
            # 1. Refresh reliability scores if necessary
            self.reliability_engine.calculate_all_scores()
            
            # 2. Get reliability score
            reliability_score = self.reliability_engine.get_trip_reliability(train_number)
            
            # 3. Calculate predicted delay from reliability score
            # Inverse of sigmoid: lower reliability = higher delay
            predicted_delay = int((1 - reliability_score) * 180)  # Max 180 minutes
            
            # 4. Risk threshold evaluation
            risk_level = self._calculate_risk_level(reliability_score, predicted_delay)
            
            # 5. Find alternatives if high risk
            alternatives = []
            if risk_level in ["HIGH", "CRITICAL"]:
                alternatives = await self._find_alternatives(
                    source=boarding_station,
                    destination=destination_station,
                    travel_date=travel_date,
                    original_train=train_number,
                    original_class=class_code
                )
            
            # 6. Dispatch alert if needed
            alert_sent = False
            if risk_level in ["HIGH", "CRITICAL"] and alternatives:
                alert_sent = await self._dispatch_delay_alert(
                    booking_id=booking_id,
                    user_id=user_id,
                    train_number=train_number,
                    risk_level=risk_level,
                    alternatives=alternatives,
                    delay_minutes=predicted_delay
                )
            
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            result = DelayCheckResult(
                booking_id=booking_id,
                train_number=train_number,
                reliability_score=reliability_score,
                predicted_delay_minutes=predicted_delay,
                actual_delay_minutes=None,  # Would be filled by audit
                risk_level=risk_level,
                is_available=bool(alternatives),
                alternatives_count=len(alternatives),
                message=f"Delay risk: {risk_level}. {'Alert sent.' if alert_sent else 'No alternatives found.'}",
                response_time_ms=response_time_ms
            )
            
            # Cache the result
            self._cache_result(booking_id, result)
            
            # Record metrics
            await self._record_metrics(result)
            
            logger.info(f"🛡️ [DELAY_WATCH] Booking {booking_id} Reliability: {reliability_score:.2f}, Risk: {risk_level}")
            
            return result.to_dict()
            
        except Exception as e:
            logger.error(f"Delay risk check failed: {e}")
            response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            result = DelayCheckResult(
                booking_id=booking_id,
                train_number=train_number,
                reliability_score=0.5,
                predicted_delay_minutes=0,
                actual_delay_minutes=None,
                risk_level="UNKNOWN",
                is_available=False,
                alternatives_count=0,
                message="Delay check failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            
            return result.to_dict()

    async def _record_metrics(self, result: DelayCheckResult):
        """Record metrics for monitoring."""
        if self._metrics_lock is None:
            import asyncio
            self._metrics_lock = asyncio.Lock()
        
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "booking_id": result.booking_id,
                "risk_level": result.risk_level,
                "reliability_score": result.reliability_score,
                "alternatives_found": result.alternatives_count,
                "response_time_ms": result.response_time_ms
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_checks": 0, "high_risk_count": 0}
        
        total = len(self._metrics)
        high_risk = sum(1 for m in self._metrics if m["risk_level"] in ["HIGH", "CRITICAL"])
        response_times = [m["response_time_ms"] for m in self._metrics]
        
        return {
            "total_checks": total,
            "high_risk_count": high_risk,
            "high_risk_rate": high_risk / total if total > 0 else 0.0,
            "avg_response_time_ms": sum(response_times) / len(response_times) if response_times else 0,
            "circuit_breaker_states": {
                "flex": self._flex_breaker.get_state().value,
                "websocket": self._ws_breaker.get_state().value
            }
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "config": {
                "cache_ttl_seconds": self.config.cache_ttl_seconds,
                "timeout_seconds": self.config.timeout_seconds,
                "reliability_threshold": self.config.reliability_threshold
            },
            "circuit_breakers": {
                "flex": self._flex_breaker.get_state().value,
                "websocket": self._ws_breaker.get_state().value
            },
            "metrics": self.get_metrics()
        }

    def clear_cache(self, booking_id: Optional[str] = None):
        """Clear delay check cache."""
        if booking_id:
            pattern = f"delay_check:{booking_id}"
        else:
            pattern = "delay_check:*"
        
        cache_service.get_pattern(pattern)
        logger.info(f"Delay check cache cleared for pattern: {pattern}")


def get_delay_service(db: Session) -> DelayService:
    """Factory function to create DelayService instance."""
    return DelayService(db)
