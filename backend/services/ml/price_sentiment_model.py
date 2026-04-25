import logging
import random
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta
from database.session import SessionLocal
from database.models import RouteSearchLog
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("ml.sentiment")

class PriceSentimentModel:
    """
    [G3.3.1] Price Sentiment & Trend Inference Model.
    Analyzes historical search yield and pricing to predict future movements.
    Powers the 'Wait vs. Buy' Advisor.
    """

    def __init__(self):
        # Circuit breaker for sentiment analysis
        self._sentiment_circuit_breaker = circuit_breaker(
            name="price_sentiment_model",
            failure_threshold=5,
            recovery_timeout=60.0
        )
        # Metrics tracking
        self._metrics = MetricsClient(
            service_name="price_sentiment_model",
            default_tags={"component": "ml"}
        )
        self._metrics.gauge("circuit_breaker_state", lambda: self._sentiment_circuit_breaker.state.value)
        self._metrics.counter("analyses_total")
        self._metrics.counter("analyses_success")
        self._metrics.counter("analyses_failed")
        self._metrics.histogram("analysis_duration_seconds")

    @track_metrics(service="price_sentiment_model", operation="get_route_sentiment")
    @_sentiment_circuit_breaker
    async def get_route_sentiment(self, src: str, dst: str) -> Dict[str, Any]:
        """
        [Child G3.3.1.2] Trend Inference Engine.
        Returns sentiment (BULLISH, BEARISH, STABLE) for a given corridor.
        """
        start_time = time.perf_counter()
        try:
            # 1. Aggregation (Child G3.3.1.1)
            history = await self._fetch_corridor_history(src, dst)
            
            if len(history) < 5:
                return {"sentiment": "STABLE", "confidence": 0.5, "advice": "Not enough data yet."}

            # 2. Inference Logic
            # Simple slope calculation based on historical costs
            prices = [h['cost'] for h in history]
            slope = (prices[-1] - prices[0]) / len(prices)
            
            if slope > 50: # Significant increase
                sentiment = "BULLISH"
                advice = "Prices are trending UP. We recommend booking NOW to lock in current rates."
                color = "#EF4444" # Red
            elif slope < -50: # Significant decrease
                sentiment = "BEARISH"
                advice = "Historically, prices for this route dip soon. If you're flexible, WAIT 2-3 days."
                color = "#10B981" # Green
            else:
                sentiment = "STABLE"
                advice = "Prices are consistent. Safe to book anytime."
                color = "#6D28D9" # Purple

            duration = time.perf_counter() - start_time
            self._metrics.histogram("analysis_duration_seconds", duration)
            self._metrics.counter("analyses_success", tags={"sentiment": sentiment})
            logger.debug(f"📊 [SENTIMENT] Analyzed {src}-{dst}: {sentiment} in {duration:.3f}s")
            
            return {
                "src": src,
                "dst": dst,
                "sentiment": sentiment,
                "advice": advice,
                "color": color,
                "predicted_delta_pct": round((slope / prices[0]) * 100, 1) if prices[0] > 0 else 0
            }
        except Exception as e:
            duration = time.perf_counter() - start_time
            self._metrics.histogram("analysis_duration_seconds", duration)
            self._metrics.counter("analyses_failed", tags={"error_type": type(e).__name__})
            logger.error(f"❌ [SENTIMENT] Analysis failed for {src}-{dst}: {e}")
            raise

    async def _fetch_corridor_history(self, src: str, dst: str) -> List[Dict[str, Any]]:
        """[Child G3.3.1.1] Fetches pricing data from SearchOutcomes."""
        # Conceptually queries specific corridor yields from last 15 days
        # Mocking with small variation for now
        base = 1200
        return [
            {"date": "2026-04-01", "cost": base + random.randint(-100, 100)} 
            for _ in range(10)
        ]

price_sentiment_model = PriceSentimentModel()

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "price_sentiment_model",
            "circuit_breaker_state": self._sentiment_circuit_breaker.state.name,
            "circuit_breaker_failures": self._sentiment_circuit_breaker.failure_count,
            "analyses_total": self._metrics.get_counter("analyses_total"),
            "analyses_success": self._metrics.get_counter("analyses_success"),
            "analyses_failed": self._metrics.get_counter("analyses_failed"),
            "analysis_duration_p50": self._metrics.get_percentile("analysis_duration_seconds", 50),
            "analysis_duration_p95": self._metrics.get_percentile("analysis_duration_seconds", 95),
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if self._sentiment_circuit_breaker.state == CircuitState.CLOSED else "degraded",
            "service": "price_sentiment_model",
            "circuit_breaker": self._sentiment_circuit_breaker.state.name,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker to closed state."""
        self._sentiment_circuit_breaker.reset()
        logger.info("🔄 [SENTIMENT] Circuit breaker reset for price sentiment model")
