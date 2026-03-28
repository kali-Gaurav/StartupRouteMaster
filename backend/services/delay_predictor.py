import logging
import asyncio
import time
import os
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("nexus.ml.delay")

class DelayPredictor:
    """
    [Task 103] Elite ML Predictor with Disk Swap (Task 87) and Async Inference.
    Optimized for 500MB VPS: Zero-impact boot and lazy resource allocation.
    """
    def __init__(self):
        self.model = None
        self.is_trained = False
        self._overflow_key = "nexus_ml_delay_predictor"
        self._executor = ThreadPoolExecutor(max_workers=1)
        self.MODEL_PATH = "models/delay_model.pkl"

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

# Global instance
delay_predictor = DelayPredictor()
