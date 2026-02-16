import logging
import pickle
import os
import time
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from backend.utils.metrics import ML_INFERENCE_LATENCY_MS

logger = logging.getLogger(__name__)

class DelayPredictor:
    """
    ML model to predict train delay minutes based on historical data.
    Uses RandomForest as scaffold; can be upgraded to XGBoost or neural nets.
    """

    MODEL_PATH = "backend/models/delay_model.pkl"

    def __init__(self):
        self.model = None
        self.is_trained = False
        # Real-time delay updates from TrainDelayed events
        self.in_memory_delay_map: Dict[int, Dict[str, Any]] = {}  # train_id -> delay info
        # Thread safety for concurrent access
        self._delay_map_lock = asyncio.Lock()
        # TTL configuration: 30 minutes for real-time delays
        self.DELAY_TTL_SECONDS = 30 * 60  # 30 minutes
        self.load_or_train_model()

    def load_or_train_model(self):
        """Load pre-trained model or train a scaffold model on synthetic data."""
        if os.path.exists(self.MODEL_PATH):
            try:
                with open(self.MODEL_PATH, 'rb') as f:
                    self.model = pickle.load(f)
                self.is_trained = True
                logger.info("Loaded pre-trained delay prediction model.")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                self.train_scaffold_model()
        else:
            self.train_scaffold_model()

    def train_scaffold_model(self):
        """Train a simple RandomForest on synthetic delay data."""
        logger.info("Training scaffold delay prediction model on synthetic data.")

        # Generate synthetic data
        np.random.seed(42)
        n_samples = 10000
        data = {
            'train_id': np.random.randint(1000, 9999, n_samples),
            'day_of_week': np.random.randint(0, 7, n_samples),
            'month': np.random.randint(1, 13, n_samples),
            'departure_hour': np.random.randint(0, 24, n_samples),
            'past_delay_avg': np.random.normal(5, 10, n_samples).clip(0),
            'weather_score': np.random.uniform(0, 1, n_samples),  # Placeholder
            'delay_minutes': np.random.exponential(5, n_samples)  # Target
        }
        df = pd.DataFrame(data)

        # Features
        features = ['train_id', 'day_of_week', 'month', 'departure_hour', 'past_delay_avg', 'weather_score']
        X = df[features]
        y = df['delay_minutes']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        logger.info(f"Scaffold model trained. MAE: {mae:.2f} minutes")

        # Save model
        os.makedirs(os.path.dirname(self.MODEL_PATH), exist_ok=True)
        with open(self.MODEL_PATH, 'wb') as f:
            pickle.dump(self.model, f)

        self.is_trained = True

    def predict_delay(self, train_id: int, day_of_week: int, month: int, departure_hour: int,
                     past_delay_avg: float = 0.0, weather_score: float = 0.5) -> float:
        """
        Predict delay minutes for a train journey.

        :param train_id: Unique train identifier
        :param day_of_week: 0=Monday, 6=Sunday
        :param month: 1-12
        :param departure_hour: Hour of departure (0-23)
        :param past_delay_avg: Average delay of this train in recent history
        :param weather_score: Weather impact score (0-1, placeholder)
        :return: Predicted delay in minutes
        """
        if not self.is_trained:
            logger.warning("Model not trained, returning 0 delay.")
            return 0.0

        features = pd.DataFrame([{
            'train_id': train_id,
            'day_of_week': day_of_week,
            'month': month,
            'departure_hour': departure_hour,
            'past_delay_avg': past_delay_avg,
            'weather_score': weather_score
        }])

        try:
            start_time = time.time()
            prediction = self.model.predict(features)[0]
            latency_ms = (time.time() - start_time) * 1000
            
            # Record ML inference latency
            if ML_INFERENCE_LATENCY_MS is not None:
                ML_INFERENCE_LATENCY_MS.labels(model='delay_predictor').observe(latency_ms)
            
            return max(0, prediction)  # Ensure non-negative
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return 0.0

    async def update_real_time_delay(self, train_id: int, delay_minutes: int, station_code: str, 
                              scheduled_departure: str, estimated_departure: str, reason: Optional[str] = None):
        """
        Update in-memory delay map from TrainDelayed events for real-time intelligence.
        Thread-safe with TTL cleanup.
        
        :param train_id: Train identifier
        :param delay_minutes: Current delay in minutes
        :param station_code: Station where delay was reported
        :param scheduled_departure: Scheduled departure time
        :param estimated_departure: Estimated departure time
        :param reason: Reason for delay (if provided)
        """
        async with self._delay_map_lock:
            # Clean up expired entries before adding new one
            await self._cleanup_expired_delays()
            
            self.in_memory_delay_map[train_id] = {
                'delay_minutes': delay_minutes,
                'station_code': station_code,
                'scheduled_departure': scheduled_departure,
                'estimated_departure': estimated_departure,
                'reason': reason,
                'last_updated': datetime.utcnow(),
                'expires_at': datetime.utcnow() + timedelta(seconds=self.DELAY_TTL_SECONDS),
                'source': 'real_time_event'
            }
            logger.info(f"Updated real-time delay for train {train_id}: {delay_minutes} minutes at {station_code} (TTL: {self.DELAY_TTL_SECONDS}s)")

    async def get_real_time_delay(self, train_id: int) -> Optional[Dict[str, Any]]:
        """
        Get real-time delay information for a train.
        Thread-safe with TTL cleanup.
        
        :param train_id: Train identifier
        :return: Delay information dict or None if not available/expired
        """
        async with self._delay_map_lock:
            # Clean up expired entries
            await self._cleanup_expired_delays()
            
            delay_info = self.in_memory_delay_map.get(train_id)
            if delay_info:
                # Double-check expiration (in case cleanup missed it)
                if datetime.utcnow() > delay_info['expires_at']:
                    del self.in_memory_delay_map[train_id]
                    return None
                return delay_info
            return None

    async def _cleanup_expired_delays(self):
        """Remove expired delay entries to prevent memory leaks."""
        now = datetime.utcnow()
        expired_trains = [
            train_id for train_id, delay_info in self.in_memory_delay_map.items()
            if now > delay_info['expires_at']
        ]
        
        for train_id in expired_trains:
            del self.in_memory_delay_map[train_id]
            logger.debug(f"Cleaned up expired delay for train {train_id}")
        
        if expired_trains:
            logger.info(f"Cleaned up {len(expired_trains)} expired delay entries")

# Global instance
delay_predictor = DelayPredictor()