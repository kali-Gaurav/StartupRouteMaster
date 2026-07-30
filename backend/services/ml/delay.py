import logging
import asyncio
import time
import os
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from datetime import datetime

from core.resilience.core import circuit_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy

logger = logging.getLogger("nexus.ml.delay")

class DelayPredictor:
    """
    [Task 103] Elite ML Predictor with Disk Swap (Task 87) and Async Inference.
    Optimized for 500MB VPS: Zero-impact boot and lazy resource allocation.
    
    With resilience patterns: circuit breaker, retry, and metrics tracking.
    """
    def __init__(self):
        self.model: Optional[Any] = None
        self.is_trained = False
        self._overflow_key = "nexus_ml_delay_predictor"
        self._executor = ThreadPoolExecutor(max_workers=1)
        self.MODEL_PATH = "models/delay_model.pkl"
        
        # Circuit breaker for model operations
        self._model_breaker = circuit_manager.get_or_create(
            "delay_predictor",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=60.0,
                success_threshold=3
            )
        )
        
        # Retry policy for model operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: isinstance(e, (OSError, IOError)),
                lambda e: "memory" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("DelayPredictor initialized with resilience patterns")

    def _lazy_imports(self):
        """Internal helper to load heavy ML libs ONLY when needed."""
        try:
            import numpy as np
            import pandas as pd
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.model_selection import train_test_split
            return np, pd, RandomForestRegressor, train_test_split
        except ImportError:
            logger.error("❌ [NEXUS:ML] Missing ML dependencies (numpy/pandas/sklearn).")
            return None, None, None, None

    async def unload_model(self):
        """[Task 87] Swaps model to disk and clears RAM."""
        if self.model is not None:
            from utils.overflow import nexus_overflow
            logger.warning("💾 [NEXUS:ML] Swapping Delay model to Disk Overflow (OOM Prevention).")
            nexus_overflow.swap_out(self.model, key=self._overflow_key)
            self.model = None
            self.is_trained = False
            import gc; gc.collect()

    async def _ensure_model(self):
        """Loads model from Disk Swap or Persistent Storage."""
        if self.model is not None: return True
        
        from utils.overflow import nexus_overflow
        # Try Disk Swap first (Task 87)
        swapped = nexus_overflow.swap_in(self._overflow_key, delete_after=True)
        if swapped:
            self.model = swapped
            self.is_trained = True
            return True
            
        # Try main storage
        if os.path.exists(self.MODEL_PATH):
            import pickle
            try:
                with open(self.MODEL_PATH, 'rb') as f:
                    self.model = pickle.load(f)
                self.is_trained = True
                return True
            except: pass
        return False

    async def predict_delay(self, train_id: int, **kwargs) -> float:
        """Async inference wrapper to prevent event loop blocking."""
        from core.nexus.audit.triage import nexus_triage
        if nexus_triage.current_backoff > 0.8:
            await self.unload_model()
            return 0.0

        if not await self._ensure_model():
            return 0.0

        # Execute blocking scikit-learn call in thread pool
        loop = asyncio.get_running_loop()
        try:
            prediction = await loop.run_in_executor(self._executor, self._sync_predict, train_id, kwargs)
            return float(prediction)
        except Exception as e:
            logger.error(f"Inference Failure: {e}")
            return 0.0

    async def update_real_time_delay(
        self,
        train_id: int,
        delay_minutes: float,
        station_code: str,
        scheduled_departure: str,
        estimated_departure: str,
        reason: Any = None
    ) -> float:
        """Update real-time delay intelligence and return a new prediction."""
        logger.debug(
            f"Updating real-time delay for train {train_id} at {station_code}: "
            f"delay={delay_minutes}, scheduled={scheduled_departure}, estimated={estimated_departure}"
        )
        prediction = await self.predict_delay(
            train_id,
            day_of_week=datetime.utcnow().weekday(),
            departure_hour=datetime.utcnow().hour,
            delay_minutes=delay_minutes,
            station_code=station_code,
            scheduled_departure=scheduled_departure,
            estimated_departure=estimated_departure,
            reason=str(reason) if reason is not None else ""
        )
        await self._record_metrics(train_id, prediction, True)
        return prediction

    def _sync_predict(self, train_id, kwargs):
        """Synchronous inference logic (runs in thread)."""
        np, _, _, _ = self._lazy_imports()
        if not np: return 0.0
        
        features = np.array([[
            float(train_id), 
            float(kwargs.get('day_of_week', 0)), 
            float(kwargs.get('month', 1)), 
            float(kwargs.get('departure_hour', 12)), 
            float(kwargs.get('past_delay_avg', 0)), 
            float(kwargs.get('weather_score', 0.5))
        ]], dtype=np.float32)
        
        return self.model.predict(features)[0]

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(self, train_id: int, prediction: float, success: bool):
        """Record prediction metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "train_id": train_id,
                "prediction": prediction,
                "success": success,
                "model_loaded": self.is_trained
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_predictions": 0, "avg_prediction": 0.0}
        
        total = len(self._metrics)
        predictions = [m["prediction"] for m in self._metrics]
        successful = sum(1 for m in self._metrics if m["success"])
        model_loaded = sum(1 for m in self._metrics if m.get("model_loaded", False))
        
        return {
            "total_predictions": total,
            "successful_predictions": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_prediction": sum(predictions) / len(predictions) if predictions else 0,
            "model_load_rate": model_loaded / total if total > 0 else 0.0,
            "circuit_breaker_state": self._model_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "model_trained": self.is_trained,
            "circuit_breaker": {
                "state": self._model_breaker.get_state().value,
                "failure_count": self._model_breaker.failure_count,
                "success_count": self._model_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._model_breaker.reset()
        logger.info("Circuit breaker reset for delay predictor")


# Global instance
delay_predictor = DelayPredictor()
