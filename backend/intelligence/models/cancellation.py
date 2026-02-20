"""
Cancellation Prediction Service - ML-Based Booking Cancellation Forecasting
============================================================================

Predicts cancellation rates for:
1. Revenue optimization (overbooking decisions)
2. Inventory management
3. Dynamic pricing adjustments
4. Risk mitigation (compensation budgeting)

Features:
- Historical pattern analysis
- Temporal features (day of week, holidays, seasonality)
- User behavior features (booking history, profile)
- Route characteristics (demand, distance, day-type)
- Model: Gradient Boosting (XGBoost/LightGBM)

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import logging
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CancellationPrediction:
    """Cancellation prediction result."""
    train_id: int
    travel_date: str
    quota_type: str
    predicted_cancellation_rate: float  # 0-1
    confidence_score: float  # 0-1 (model confidence)
    contributing_factors: Dict[str, float]  # Feature importance
    recommendation: str  # "safe_to_overbook", "normal", "high_risk"


class CancellationPredictor:
    """
    ML model for predicting cancellation rates.
    
    Uses historical booking data to forecast cancellations
    for revenue optimization and overbooking decisions.
    """
    
    # Cancellation rate targets by quota type
    EXPECTED_CANCELLATION_RATES = {
        'general': 0.08,        # 8% expected cancellations
        'tatkal': 0.05,         # 5% (lower - purchased same day)
        'ladies': 0.06,
        'senior_citizen': 0.10, # 10% (higher - medical/emergency)
        'defence': 0.04,        # 4% (lowest)
        'foreign_tourist': 0.12, # 12% (higher - travel plans change)
    }
    
    # Risk thresholds
    SAFE_THRESHOLD = 0.06   # <6%: safe to overbook
    HIGH_RISK_THRESHOLD = 0.12  # >12%: high risk
    
    def __init__(self):
        """Initialize cancellation predictor."""
        self.model = None
        self.is_trained = False
        self.feature_names = []
        self.logger = logging.getLogger(__name__)
    
    def train_scaffold_model(self):
        """
        Train a scaffold model on synthetic data.
        
        In production: train on 12+ months of historical booking data
        """
        logger.info("Training cancellation prediction scaffold model")
        
        # Synthetic training data
        X_train = self._generate_synthetic_features(5000)
        y_train = self._generate_synthetic_targets(len(X_train))
        
        try:
            from lightgbm import LGBMRegressor
            
            self.model = LGBMRegressor(
                n_estimators=100,
                learning_rate=0.05,
                max_depth=6,
                num_leaves=31,
                random_state=42,
                verbose=-1,
            )
            
            self.model.fit(X_train, y_train)
            self.is_trained = True
            self.feature_names = self._get_feature_names()
            
            logger.info("Cancellation prediction model trained successfully")
            
        except ImportError:
            logger.warning("LightGBM not installed; using baseline model")
            self.is_trained = True
    
    def load_or_train_model(self):
        """Load saved model or train a new one."""
        try:
            with open("models/cancellation_predictor.pkl", "rb") as f:
                self.model = pickle.load(f)
                self.is_trained = True
                logger.info("Loaded cancellation predictor model")
        except FileNotFoundError:
            self.train_scaffold_model()
    
    def predict_cancellation_rate(
        self,
        train_id: int,
        travel_date: str,
        quota_type: str,
        days_to_departure: int,
        booking_velocity: float,
        route_popularity: float,
        demand_forecast: float,
        historical_cancellation_rate: float,
    ) -> CancellationPrediction:
        """
        Predict cancellation rate for a train-quota combination.
        
        Inputs:
        - train_id: Train identifier
        - travel_date: Travel date
        - quota_type: Booking quota (general, tatkal, etc.)
        - days_to_departure: Days until departure
        - booking_velocity: Bookings per hour in last 24h
        - route_popularity: Route popularity score (0-1)
        - demand_forecast: Demand forecast (0-1)
        - historical_cancellation_rate: Average historical rate
        
        Returns:
        - CancellationPrediction with rate, confidence, factors
        """
        # Build feature vector
        features = self._build_features(
            train_id=train_id,
            travel_date=travel_date,
            quota_type=quota_type,
            days_to_departure=days_to_departure,
            booking_velocity=booking_velocity,
            route_popularity=route_popularity,
            demand_forecast=demand_forecast,
            historical_cancellation_rate=historical_cancellation_rate,
        )
        
        # Make prediction
        if self.is_trained and self.model:
            try:
                predicted_rate = float(self.model.predict(np.array([features]))[0])
                predicted_rate = np.clip(predicted_rate, 0, 0.3)  # Reasonable bounds
                confidence = self._calculate_confidence(features)
            except Exception as e:
                logger.error(f"Prediction error: {e}; using baseline")
                predicted_rate = self.EXPECTED_CANCELLATION_RATES.get(quota_type, 0.08)
                confidence = 0.5
        else:
            # Baseline prediction
            predicted_rate = self.EXPECTED_CANCELLATION_RATES.get(quota_type, 0.08)
            confidence = 0.5
        
        # Determine recommendation
        if predicted_rate <= self.SAFE_THRESHOLD:
            recommendation = "safe_to_overbook"
        elif predicted_rate >= self.HIGH_RISK_THRESHOLD:
            recommendation = "high_risk_no_overbook"
        else:
            recommendation = "moderate_caution"
        
        # Calculate contributing factors
        factors = self._calculate_feature_importance(features)
        
        prediction = CancellationPrediction(
            train_id=train_id,
            travel_date=travel_date,
            quota_type=quota_type,
            predicted_cancellation_rate=predicted_rate,
            confidence_score=confidence,
            contributing_factors=factors,
            recommendation=recommendation,
        )
        
        logger.info(
            f"Cancellation prediction for train {train_id} ({quota_type}): "
            f"{predicted_rate:.2%} (confidence: {confidence:.2f})"
        )
        
        return prediction
    
    def _build_features(
        self,
        train_id: int,
        travel_date: str,
        quota_type: str,
        days_to_departure: int,
        booking_velocity: float,
        route_popularity: float,
        demand_forecast: float,
        historical_cancellation_rate: float,
    ) -> np.ndarray:
        """Build feature vector for model."""
        
        # Parse travel date
        try:
            travel_dt = pd.to_datetime(travel_date)
        except:
            travel_dt = datetime.now()
        
        # Temporal features
        day_of_week = travel_dt.dayofweek  # 0-6
        month = travel_dt.month
        is_weekend = day_of_week >= 5
        is_holiday_season = month in [12, 1, 7, 8]  # Approximation
        
        # Quota encoding
        quota_map = {
            'general': 0,
            'tatkal': 1,
            'ladies': 2,
            'senior_citizen': 3,
            'defence': 4,
            'foreign_tourist': 5,
        }
        quota_encoded = quota_map.get(quota_type, 0)
        
        # Feature vector
        features = np.array([
            # Temporal
            day_of_week,
            month,
            float(is_weekend),
            float(is_holiday_season),
            days_to_departure,
            
            # Train/Route
            train_id % 1000,  # Train number modulo
            route_popularity,
            
            # Quota
            quota_encoded,
            
            # Demand & Booking
            booking_velocity,
            demand_forecast,
            
            # Historical
            historical_cancellation_rate,
            
            # Interactions
            booking_velocity * demand_forecast,
            days_to_departure * route_popularity,
        ], dtype=np.float32)
        
        return features
    
    def _generate_synthetic_features(self, n_samples: int) -> np.ndarray:
        """Generate synthetic features for model training."""
        features = []
        
        for _ in range(n_samples):
            day_of_week = np.random.randint(0, 7)
            month = np.random.randint(1, 13)
            is_weekend = float(day_of_week >= 5)
            is_holiday = float(month in [12, 1, 7, 8])
            days_to_dep = np.random.randint(1, 60)
            train_id = np.random.randint(1, 100)
            route_pop = np.random.uniform(0.3, 1.0)
            quota = np.random.randint(0, 6)
            velocity = np.random.uniform(0, 10)
            demand = np.random.uniform(0, 1)
            hist_cancel = np.random.uniform(0.04, 0.15)
            
            feature = np.array([
                day_of_week, month, is_weekend, is_holiday, days_to_dep,
                train_id, route_pop, quota, velocity, demand, hist_cancel,
                velocity * demand,
                days_to_dep * route_pop,
            ], dtype=np.float32)
            
            features.append(feature)
        
        return np.array(features)
    
    def _generate_synthetic_targets(self, n_samples: int) -> np.ndarray:
        """Generate synthetic targets for model training."""
        targets = []
        
        for _ in range(n_samples):
            # Synthetic cancellation rate (4-15%)
            base_rate = np.random.uniform(0.04, 0.15)
            
            # Add noise
            noise = np.random.normal(0, 0.01)
            
            rate = np.clip(base_rate + noise, 0.02, 0.25)
            targets.append(rate)
        
        return np.array(targets)
    
    def _get_feature_names(self) -> List[str]:
        """Get feature names for interpretability."""
        return [
            'day_of_week', 'month', 'is_weekend', 'is_holiday_season',
            'days_to_departure', 'train_id', 'route_popularity',
            'quota_type', 'booking_velocity', 'demand_forecast',
            'historical_cancellation', 'velocity_demand_interaction',
            'days_popularity_interaction',
        ]
    
    def _calculate_confidence(self, features: np.ndarray) -> float:
        """
        Calculate model confidence in prediction.
        
        Higher confidence when:
        - More days to departure (more data collected)
        - Higher booking velocity (more bookings = clearer pattern)
        - Route popularity is extreme (clearer patterns)
        """
        days_to_dep = features[4]
        velocity = features[8]
        route_pop = features[6]
        
        # Base confidence from days to departure
        conf = min(1.0, days_to_dep / 30)
        
        # Boost from velocity
        conf += min(0.3, velocity / 10)
        
        # Boost from route popularity extremity
        popularity_extreme = 1 - abs(route_pop - 0.5)
        conf += popularity_extreme * 0.2
        
        return min(1.0, conf)
    
    def _calculate_feature_importance(self, features: np.ndarray) -> Dict[str, float]:
        """
        Calculate which factors most influenced the prediction.
        
        Simplified: returns feature * weight analysis
        """
        weights = np.array([
            0.15,  # day_of_week
            0.12,  # month
            0.08,  # is_weekend
            0.10,  # is_holiday_season
            0.18,  # days_to_departure (very important)
            0.05,  # train_id
            0.10,  # route_popularity
            0.05,  # quota_type
            0.12,  # booking_velocity
            0.15,  # demand_forecast
            0.10,  # historical_cancellation
            0.05,  # interactions
            0.05,
        ])
        
        importance = np.abs(features * weights)
        
        return {
            name: float(imp)
            for name, imp in zip(self._get_feature_names(), importance)
            if imp > 0.01
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

cancellation_predictor = CancellationPredictor()
