import asyncio
import logging
import time
from typing import Dict, Set, List
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from services.jit_manager import jit_manager
from core.ml_models.route_predictor import route_predictor
from services.intelligence.feedback_loop_enhanced import feedback_loop
from core.resilience.core import circuit_manager, CircuitConfig
from core.resilience.retry import RetryPolicy

logger = logging.getLogger("shadow-warmer")

class ShadowWarmer:
    """
    Subtask 1.13: Predictive Cache Pre-fetching.
    """
    
    def __init__(self):
        self.warmed_routes: Set[str] = set()
        
        # Circuit breaker for ML model predictions
        self._ml_breaker = circuit_manager.get_or_create(
            "shadow_warmer_ml",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=3
            )
        )
        
        # Circuit breaker for cache operations
        self._cache_breaker = circuit_manager.get_or_create(
            "shadow_warmer_cache",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=60.0,
                success_threshold=3
            )
        )
        
        # Retry policy for prefetch operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=True,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "cache" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("ShadowWarmer initialized with resilience patterns")

    async def warm_by_intent(self, client_id: str, intent: str, path: str):
        # VITAL: Skip warming for health/docs/root
        if any(x in path for x in ["health", "docs", "openapi.json"]) or path == "/":
            return

        await feedback_loop.record_prediction(client_id, intent, path)
        
        from core.infrastructure.metrics import jit_metrics
        jit_metrics.prewarms_triggered += 1
        
        available_nodes = jit_manager.nodes.keys()
        
        if intent == "SEARCH":
            if "DATABASE" in available_nodes:
                asyncio.create_task(jit_manager.ensure_ready("DATABASE"))
            if "CACHE" in available_nodes:
                asyncio.create_task(jit_manager.ensure_ready("CACHE"))
            asyncio.create_task(self._prefetch_user_context(client_id))
            
        elif intent == "STATUS":
            if "GRAPH" in available_nodes:
                asyncio.create_task(jit_manager.ensure_ready("GRAPH"))
            if "ML_MODELS" in available_nodes:
                asyncio.create_task(jit_manager.ensure_ready("ML_MODELS"))

    async def _prefetch_user_context(self, client_id: str):
        try:
            from services.multi_layer_cache import multi_layer_cache
            cache_key = f"user_recent:{client_id}"
            await multi_layer_cache.get(cache_key)
        except Exception: pass

    async def predictive_graph_warm(self, origin_code: str):
        predictions = await route_predictor.predict_top_destinations(origin_code)
        for dest, prob in predictions:
            if prob > 0.8:
                pass
    
    async def _record_metrics(self, operation_type: str, success: bool, error: str = None):
        """Record metrics for shadow warmer operations."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "error": error
            })
    
    def get_metrics(self) -> dict:
        """Get service metrics."""
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
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_type,
            "warmed_routes_count": len(self.warmed_routes),
            "circuit_breaker_ml_state": self._ml_breaker.get_state().value,
            "circuit_breaker_cache_state": self._cache_breaker.get_state().value
        }
    
    def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "ml": {
                    "state": self._ml_breaker.get_state().value,
                    "failure_count": self._ml_breaker.failure_count,
                    "success_count": self._ml_breaker.success_count
                },
                "cache": {
                    "state": self._cache_breaker.get_state().value,
                    "failure_count": self._cache_breaker.failure_count,
                    "success_count": self._cache_breaker.success_count
                }
            },
            "metrics": self.get_metrics()
        }
    
    def reset_circuit_breakers(self):
        """Reset circuit breakers."""
        self._ml_breaker.reset()
        self._cache_breaker.reset()
        logger.info("Circuit breakers reset for shadow_warmer")

shadow_warmer = ShadowWarmer()
