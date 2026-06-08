import logging
import asyncio
import time
import os
import pickle
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("nexus.ml.tatkal")

class TatkalDemandPredictor:
    """
    [Task 103] Elite ML Predictor: Seat Sellout Probability.
    Disk Swap (Task 87) & Async Executor.
    Optimized for 500MB VPS: Zero-impact boot.
    """
    def __init__(self):
        self.model: Any = None
        self.is_trained = False
        self._overflow_key = "nexus_ml_tatkal_predictor"
        self._executor = ThreadPoolExecutor(max_workers=1)
        self.model_path = "models/tatkal_demand_model.pkl"

    def _lazy_imports(self):
        try:
            import numpy as np
            import pandas as pd
            from sklearn.ensemble import RandomForestRegressor
            return np, pd, RandomForestRegressor
        except ImportError:
            logger.error("❌ [NEXUS:ML] Tatkal dependencies (numpy/pandas/sklearn) unavailable.")
            return None, None, None

    async def unload_model(self):
        """[Task 87] Flush model to Disk Overflow."""
        if self.model is not None:
            from utils.overflow import nexus_overflow
            logger.warning("💾 [NEXUS:ML] Swapping Tatkal model to Disk Overflow.")
            nexus_overflow.swap_out(self.model, key=self._overflow_key)
            self.model = None
            self.is_trained = False
            import gc; gc.collect()

    async def _ensure_model(self):
        if self.model is not None: return True
        
        from utils.overflow import nexus_overflow
        swapped = nexus_overflow.swap_in(self._overflow_key, delete_after=True)
        if swapped:
            self.model = swapped
            self.is_trained = True
            return True
            
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                self.is_trained = True
                return True
            except: pass
        return False

    async def predict_sellout_probability(self, features: Dict[str, Any]) -> float:
        """Async inference for Tatkal risk."""
        from core.nexus.audit.triage import nexus_triage
        if nexus_triage.current_backoff > 0.8:
            await self.unload_model()
            return 0.5 # Neutral fallback

        if not await self._ensure_model():
            return 0.5

        loop = asyncio.get_running_loop()
        try:
            prob = await loop.run_in_executor(self._executor, self._sync_predict, features)
            return float(prob)
        except Exception as e:
            logger.error(f"Tatkal Inference Failure: {e}")
            return 0.5

    def _sync_predict(self, features):
        np, _, _ = self._lazy_imports()
        if not np: return 0.5
        
        # Exact order from training [Task 48.7 audit]
        feature_order = [
            'hours_to_departure', 'booking_velocity_last_24h', 'route_popularity_score',
            'seasonality_factor', 'day_of_week', 'month', 'is_holiday_season',
            'current_occupancy_rate', 'price_premium', 'competition_factor'
        ]
        
        if self.model is None:
            return 0.5
        f_arr = np.array([[float(features.get(k, 0.0)) for k in feature_order]], dtype=np.float32)
        prob = self.model.predict(f_arr)[0]
        return float(np.clip(prob, 0, 1))

    # Support sync wrapper for legacy dashboard calls if needed
    def get_tatkal_recommendation(self, route_info, current_time):
         # Note: This involves a sync-wrapper for async call
         # For Elite V3, we use direct async calls. 
         # Placeholder to prevent crash in legacy dash.
         return {"sellout_probability": 0.5, "urgency_level": "medium", "action": "Sync-Layer-Dormant"}

    def load_model(self) -> bool:
        """Sync wrapper to warm up the predictor in sync contexts."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                logger.debug("Cannot sync-load Tatkal model while event loop is running.")
                return False

            new_loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(new_loop)
                return new_loop.run_until_complete(self._ensure_model())
            finally:
                new_loop.close()
        except Exception as e:
            logger.error(f"Failed to load Tatkal model synchronously: {e}")
            return False

# Global instance
tatkal_demand_predictor = TatkalDemandPredictor()
