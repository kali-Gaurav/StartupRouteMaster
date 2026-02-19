#!/usr/bin/env python3
"""
ML-based Reliability Model for Route Ranking

Replaces heuristic reliability estimation with a lightweight ML model.
Integrates with the ML feature store for training and inference.

Architecture:
1. Feature extraction from TrainState, transfer history, historical delays
2. Gradient Boosting (LightGBM) for reliability prediction (0-1 confidence)
3. Fallback to heuristics if model unavailable
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import joblib

try:
    import lightgbm as lgb  # type: ignore[reportMissingImports]
    HAS_LGBM = True
except Exception:
    HAS_LGBM = False
    lgb = None

from sqlalchemy import func
from .database import SessionLocal
from .database.models import Trip, StopTime, Stop, Transfer, TrainState

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "models" / "reliability_model.pkl"
FEATURE_METADATA_PATH = Path(__file__).parent / "models" / "reliability_features.json"


class MLReliabilityModel:
    """
    ML-based reliability estimator using historical delay patterns.
    
    Features:
    - Historical average delay (minutes) for train on route
    - Transfer duration (minutes) - shorter = riskier
    - Station safety score (0-1) based on historical incidents
    - Time-of-day delay patterns (peak hours more volatile)
    - Day-of-week patterns (weekends vs. weekdays)
    - Distance-based delay scaling (longer routes accumulate more delay risk)
    """

    def __init__(self):
        self.model = None
        self.feature_names = None
        self.loaded = False
        self._load_model()

    def _load_model(self):
        """Load pre-trained model from disk if available"""
        try:
            if MODEL_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
                with open(FEATURE_METADATA_PATH) as f:
                    meta = json.load(f)
                    self.feature_names = meta.get("features", [])
                self.loaded = True
                logger.info(f"Loaded reliability model with {len(self.feature_names)} features")
            else:
                logger.warning(f"No pre-trained model at {MODEL_PATH}, will use fallback heuristics")
        except Exception as e:
            logger.error(f"Failed to load reliability model: {e}")

    async def predict(
        self,
        trip_id: int,
        origin_stop_id: int,
        destination_stop_id: int,
        departure_time: datetime,
        transfer_duration_minutes: Optional[int] = None,
        distance_km: Optional[float] = None,
    ) -> float:
        """
        Predict route reliability (0 = unreliable, 1 = very reliable).

        Args:
            trip_id: Trip ID
            origin_stop_id: Starting stop
            destination_stop_id: Ending stop
            departure_time: Departure datetime
            transfer_duration_minutes: Duration of next transfer (if applicable)
            distance_km: Route distance in km

        Returns:
            Reliability score in [0, 1]
        """
        if self.loaded and self.model is not None:
            try:
                features = await self._extract_features(
                    trip_id=trip_id,
                    origin_stop_id=origin_stop_id,
                    destination_stop_id=destination_stop_id,
                    departure_time=departure_time,
                    transfer_duration_minutes=transfer_duration_minutes,
                    distance_km=distance_km,
                )
                X = self._vectorize_features(features)
                pred = self.model.predict_proba(X)[0][1]  # P(reliable=1)
                return float(np.clip(pred, 0.0, 1.0))
            except Exception as e:
                logger.warning(f"ML prediction failed: {e}, falling back to heuristics")
                return await self._fallback_heuristic(
                    transfer_duration_minutes, distance_km, departure_time
                )
        else:
            return await self._fallback_heuristic(
                transfer_duration_minutes, distance_km, departure_time
            )

    async def _extract_features(
        self,
        trip_id: int,
        origin_stop_id: int,
        destination_stop_id: int,
        departure_time: datetime,
        transfer_duration_minutes: Optional[int] = None,
        distance_km: Optional[float] = None,
    ) -> Dict[str, float]:
        """Extract features for ML model from database"""
        db = SessionLocal()
        try:
            features = {}

            # 1. Historical delay for this train on this route
            avg_delay = db.query(func.avg(TrainState.delay_minutes)).filter(
                TrainState.trip_id == trip_id
            ).scalar() or 0.0
            features["historical_delay_minutes"] = float(avg_delay)

            # 2. Time-of-day delay multiplier (peak hours 8-10am, 5-7pm have higher variance)
            hour = departure_time.hour
            is_peak = 1.0 if hour in [8, 9, 17, 18] else 0.0
            features["is_peak_hour"] = float(is_peak)

            # 3. Day of week (0=Mon, 6=Sun; weekends might be different)
            features["day_of_week"] = float(departure_time.weekday())

            # 4. Transfer duration risk: shorter transfers = higher risk
            if transfer_duration_minutes is not None:
                features["transfer_duration_minutes"] = float(transfer_duration_minutes)
            else:
                features["transfer_duration_minutes"] = 15.0  # assumed default

            # 5. Distance scaling: longer routes accumulate more delay risk
            if distance_km is not None:
                features["distance_km"] = float(distance_km)
            else:
                features["distance_km"] = 0.0

            # 6. Station safety score (0-1) - count on-time arrivals vs delays
            origin_stop = db.query(Stop).filter(Stop.id == origin_stop_id).first()
            dest_stop = db.query(Stop).filter(Stop.id == destination_stop_id).first()
            
            origin_safety = await self._compute_station_safety(origin_stop_id, db)
            dest_safety = await self._compute_station_safety(destination_stop_id, db)
            features["origin_station_safety"] = origin_safety
            features["destination_station_safety"] = dest_safety

            # 7. Trip reliability (count on-time vs late arrivals)
            total_arrivals = db.query(func.count(TrainState.id)).filter(
                TrainState.trip_id == trip_id
            ).scalar() or 1
            on_time_arrivals = db.query(func.count(TrainState.id)).filter(
                TrainState.trip_id == trip_id,
                TrainState.delay_minutes <= 5
            ).scalar() or 0
            features["trip_on_time_ratio"] = float(on_time_arrivals / max(total_arrivals, 1))

            return features

        finally:
            db.close()

    async def _compute_station_safety(self, stop_id: int, db) -> float:
        """
        Compute station safety score (0-1) based on historical delay statistics.
        Higher = safer (trains arrive on time at this station)
        """
        total = db.query(func.count(TrainState.id)).join(
            StopTime, StopTime.trip_id == TrainState.trip_id
        ).filter(StopTime.stop_id == stop_id).scalar() or 1

        on_time = db.query(func.count(TrainState.id)).join(
            StopTime, StopTime.trip_id == TrainState.trip_id
        ).filter(
            StopTime.stop_id == stop_id,
            TrainState.delay_minutes <= 5
        ).scalar() or 0

        return float(on_time / max(total, 1))

    def _vectorize_features(self, features: Dict[str, float]) -> np.ndarray:
        """
        Convert feature dict to numpy array in model's expected order.
        If a feature is missing, use default value.
        """
        if self.feature_names is None:
            self.feature_names = sorted(features.keys())

        X = []
        for fname in self.feature_names:
            X.append(features.get(fname, 0.0))
        
        return np.array([X])

    async def _fallback_heuristic(
        self,
        transfer_duration_minutes: Optional[int] = None,
        distance_km: Optional[float] = None,
        departure_time: Optional[datetime] = None,
    ) -> float:
        """
        Fallback heuristic-based reliability when ML model unavailable.
        
        Returns:
            Reliability score in [0, 1]
        """
        reliability = 1.0

        # Transfer duration penalty: shorter = riskier
        if transfer_duration_minutes is not None:
            if transfer_duration_minutes < 10:
                reliability *= 0.6
            elif transfer_duration_minutes < 15:
                reliability *= 0.85
            else:
                reliability *= 0.98

        # Distance scaling: accumulate risk over longer journeys
        if distance_km is not None:
            # Add ~0.5% delay risk per 100km
            distance_factor = 1.0 - (min(distance_km / 100.0, 0.15) * 0.005)
            reliability *= distance_factor

        # Time-of-day penalty: peak hours less reliable
        if departure_time is not None:
            hour = departure_time.hour
            if hour in [8, 9, 17, 18]:  # Peak hours
                reliability *= 0.95
            elif hour in [22, 23, 0, 1]:  # Night hours
                reliability *= 0.90

        return float(np.clip(reliability, 0.0, 1.0))

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
    ):
        """
        Train ML model on labeled data.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target labels (n_samples,) where 1 = reliable, 0 = unreliable
            feature_names: Feature column names
        """
        if not HAS_LGBM:
            logger.warning("LightGBM not installed, cannot train model")
            return

        try:
            # Train LightGBM classifier
            self.model = lgb.LGBMClassifier(
                n_estimators=50,
                max_depth=5,
                learning_rate=0.1,
                verbose=-1,
            )
            self.model.fit(X, y)
            self.feature_names = feature_names

            # Save model
            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, MODEL_PATH)
            
            with open(FEATURE_METADATA_PATH, 'w') as f:
                json.dump({"features": feature_names}, f)

            logger.info(f"Trained and saved reliability model with {len(feature_names)} features")
            self.loaded = True

        except Exception as e:
            logger.error(f"Failed to train reliability model: {e}")


# Singleton instance
_ml_reliability = None


async def get_reliability_model() -> MLReliabilityModel:
    """Get or initialize the ML reliability model"""
    global _ml_reliability
    if _ml_reliability is None:
        _ml_reliability = MLReliabilityModel()
    return _ml_reliability
