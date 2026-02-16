#!/usr/bin/env python3
"""
RouteMaster Shadow Inference Service
====================================

This service provides ML predictions in shadow mode:
- No impact on production user experience
- Logs predictions vs actual outcomes
- Enables offline evaluation and calibration
- Safe for production deployment

Architecture:
User Request → Production Logic → Shadow ML Prediction → Logging Only
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import aiohttp
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge

# Metrics
SHADOW_PREDICTIONS_TOTAL = Counter(
    'shadow_predictions_total',
    'Total shadow predictions made',
    ['model_type', 'prediction_type']
)

SHADOW_PREDICTION_LATENCY = Histogram(
    'shadow_prediction_latency_seconds',
    'Time spent making shadow predictions',
    ['model_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

SHADOW_LOGGING_ERRORS = Counter(
    'shadow_logging_errors_total',
    'Total errors logging shadow predictions',
    ['error_type']
)

class ShadowInferenceService:
    """Shadow inference service for safe ML evaluation"""

    def __init__(self,
                 redis_url: str = "redis://localhost:6379",
                 ml_service_url: str = "http://localhost:8001",
                 enable_shadow: bool = True):
        self.redis = redis.from_url(redis_url)
        self.ml_service_url = ml_service_url
        self.enable_shadow = enable_shadow
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def predict_delay_shadow(self,
                                  search_id: str,
                                  route_features: Dict[str, Any]) -> Optional[float]:
        """
        Predict delay in shadow mode - no production impact

        Args:
            search_id: Unique search identifier
            route_features: Feature dictionary for prediction

        Returns:
            Predicted delay in minutes, or None if prediction fails
        """
        if not self.enable_shadow:
            return None

        try:
            start_time = datetime.utcnow()

            # Call ML service for prediction
            prediction = await self._call_ml_service(
                model_type="delay_prediction",
                features=route_features
            )

            latency = (datetime.utcnow() - start_time).total_seconds()

            # Log shadow prediction
            await self._log_shadow_prediction(
                search_id=search_id,
                model_type="delay_prediction",
                prediction=prediction,
                latency=latency,
                features=route_features
            )

            SHADOW_PREDICTIONS_TOTAL.labels(
                model_type="delay_prediction",
                prediction_type="delay_minutes"
            ).inc()

            SHADOW_PREDICTION_LATENCY.labels(
                model_type="delay_prediction"
            ).observe(latency)

            return prediction

        except Exception as e:
            logging.error(f"Shadow delay prediction failed for {search_id}: {e}")
            SHADOW_LOGGING_ERRORS.labels(error_type="delay_prediction").inc()
            return None

    async def predict_tatkal_shadow(self,
                                   search_id: str,
                                   route_features: Dict[str, Any]) -> Optional[float]:
        """
        Predict Tatkal booking probability in shadow mode

        Args:
            search_id: Unique search identifier
            route_features: Feature dictionary for prediction

        Returns:
            Predicted Tatkal booking probability (0.0-1.0), or None if fails
        """
        if not self.enable_shadow:
            return None

        try:
            start_time = datetime.utcnow()

            # Call ML service for prediction
            prediction = await self._call_ml_service(
                model_type="tatkal_prediction",
                features=route_features
            )

            latency = (datetime.utcnow() - start_time).total_seconds()

            # Log shadow prediction
            await self._log_shadow_prediction(
                search_id=search_id,
                model_type="tatkal_prediction",
                prediction=prediction,
                latency=latency,
                features=route_features
            )

            SHADOW_PREDICTIONS_TOTAL.labels(
                model_type="tatkal_prediction",
                prediction_type="tatkal_probability"
            ).inc()

            SHADOW_PREDICTION_LATENCY.labels(
                model_type="tatkal_prediction"
            ).observe(latency)

            return prediction

        except Exception as e:
            logging.error(f"Shadow Tatkal prediction failed for {search_id}: {e}")
            SHADOW_LOGGING_ERRORS.labels(error_type="tatkal_prediction").inc()
            return None

    async def _call_ml_service(self,
                              model_type: str,
                              features: Dict[str, Any]) -> float:
        """
        Call ML service for prediction

        Args:
            model_type: Type of model (delay_prediction, tatkal_prediction)
            features: Feature dictionary

        Returns:
            Prediction value

        Raises:
            Exception: If ML service call fails
        """
        if not self.session:
            raise RuntimeError("HTTP session not initialized")

        url = f"{self.ml_service_url}/predict/{model_type}"

        async with self.session.post(url, json=features) as response:
            if response.status != 200:
                raise RuntimeError(f"ML service returned {response.status}")

            result = await response.json()
            return result.get("prediction", 0.0)

    async def _log_shadow_prediction(self,
                                    search_id: str,
                                    model_type: str,
                                    prediction: float,
                                    latency: float,
                                    features: Dict[str, Any]):
        """
        Log shadow prediction for later analysis

        Args:
            search_id: Search identifier
            model_type: Type of model
            prediction: Prediction value
            latency: Prediction latency in seconds
            features: Input features
        """
        try:
            log_entry = {
                "search_id": search_id,
                "model_type": model_type,
                "prediction": prediction,
                "latency_seconds": latency,
                "timestamp": datetime.utcnow().isoformat(),
                "features": features
            }

            # Store in Redis for fast access
            key = f"shadow:{search_id}:{model_type}"
            await self.redis.setex(
                key,
                86400 * 7,  # 7 days TTL
                json.dumps(log_entry)
            )

            # Also publish to Kafka for long-term storage
            # This would be implemented based on your Kafka setup

        except Exception as e:
            logging.error(f"Failed to log shadow prediction: {e}")
            SHADOW_LOGGING_ERRORS.labels(error_type="logging").inc()

    async def get_shadow_prediction(self,
                                   search_id: str,
                                   model_type: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve logged shadow prediction for analysis

        Args:
            search_id: Search identifier
            model_type: Type of model

        Returns:
            Shadow prediction log entry, or None if not found
        """
        try:
            key = f"shadow:{search_id}:{model_type}"
            data = await self.redis.get(key)

            if data:
                return json.loads(data)

            return None

        except Exception as e:
            logging.error(f"Failed to retrieve shadow prediction: {e}")
            return None

class BaselineHeuristicModels:
    """Baseline heuristic models for comparison"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)

    async def predict_delay_baseline(self,
                                    route_features: Dict[str, Any]) -> float:
        """
        Baseline delay prediction using simple heuristics

        Strategy:
        - Use historical averages by route and time
        - Add seasonal adjustments
        - Simple regression fallback
        """
        try:
            # Get route-specific historical average
            route_key = f"{route_features['origin_station']}_{route_features['destination_station']}"
            historical_avg = await self._get_route_delay_average(route_key)

            if historical_avg:
                # Apply time-of-day adjustment
                time_multiplier = self._get_time_multiplier(route_features['search_hour'])
                seasonal_adjustment = self._get_seasonal_adjustment(route_features['is_peak_season'])

                prediction = historical_avg * time_multiplier * seasonal_adjustment
                return max(0, min(prediction, 300))  # Clamp to 0-300 minutes

            # Fallback: simple regression based on distance
            distance_km = route_features.get('distance_km', 0)
            return max(0, distance_km * 0.1)  # 0.1 minutes per km

        except Exception as e:
            logging.error(f"Baseline delay prediction failed: {e}")
            return 0.0

    async def predict_tatkal_baseline(self,
                                     route_features: Dict[str, Any]) -> float:
        """
        Baseline Tatkal prediction using historical patterns

        Strategy:
        - Historical Tatkal booking rate by route
        - Adjust for time to travel and day of week
        - Price sensitivity factor
        """
        try:
            # Get route-specific Tatkal booking rate
            route_key = f"{route_features['origin_station']}_{route_features['destination_station']}"
            historical_rate = await self._get_route_tatkal_rate(route_key)

            if historical_rate is not None:
                # Apply adjustments
                time_adjustment = self._get_urgency_multiplier(route_features['days_to_travel'])
                day_adjustment = self._get_day_multiplier(route_features['search_day_of_week'])
                price_adjustment = self._get_price_sensitivity(route_features)

                prediction = historical_rate * time_adjustment * day_adjustment * price_adjustment
                return max(0.0, min(prediction, 1.0))  # Clamp to 0-1 probability

            # Fallback: distance-based estimate
            distance_km = route_features.get('distance_km', 0)
            return min(0.3, distance_km / 2000)  # Max 30% for very long routes

        except Exception as e:
            logging.error(f"Baseline Tatkal prediction failed: {e}")
            return 0.0

    async def _get_route_delay_average(self, route_key: str) -> Optional[float]:
        """Get historical average delay for route"""
        try:
            # This would query your delay history database
            # Placeholder implementation
            return 15.0  # 15 minutes average
        except Exception:
            return None

    async def _get_route_tatkal_rate(self, route_key: str) -> Optional[float]:
        """Get historical Tatkal booking rate for route"""
        try:
            # This would query your booking history database
            # Placeholder implementation
            return 0.25  # 25% Tatkal booking rate
        except Exception:
            return None

    def _get_time_multiplier(self, hour: int) -> float:
        """Time-of-day delay multiplier"""
        if 6 <= hour <= 9:  # Morning peak
            return 1.3
        elif 16 <= hour <= 19:  # Evening peak
            return 1.2
        elif 22 <= hour <= 4:  # Night
            return 0.8
        else:
            return 1.0

    def _get_seasonal_adjustment(self, is_peak_season: bool) -> float:
        """Seasonal delay adjustment"""
        return 1.4 if is_peak_season else 1.0

    def _get_urgency_multiplier(self, days_to_travel: int) -> float:
        """Urgency multiplier for Tatkal prediction"""
        if days_to_travel <= 1:
            return 2.0  # Very urgent
        elif days_to_travel <= 3:
            return 1.5  # Urgent
        elif days_to_travel <= 7:
            return 1.2  # Somewhat urgent
        else:
            return 0.8  # Not urgent

    def _get_day_multiplier(self, day_of_week: int) -> float:
        """Day of week adjustment for Tatkal"""
        if day_of_week >= 5:  # Weekend
            return 1.3
        else:
            return 1.0

    def _get_price_sensitivity(self, features: Dict[str, Any]) -> float:
        """Price sensitivity adjustment"""
        avg_price = features.get('avg_price_per_km', 0)
        if avg_price > 2.0:  # Expensive route
            return 1.2  # More likely to book Tatkal
        else:
            return 1.0

# Integration example for route engine
async def integrate_shadow_inference(search_id: str, route_features: Dict[str, Any]):
    """
    Example integration in route search pipeline

    This would be called from your route engine after search processing
    """

    # Production logic (unchanged)
    production_results = await process_route_search(route_features)

    # Shadow inference (no user impact)
    async with ShadowInferenceService() as shadow:
        # ML predictions
        ml_delay = await shadow.predict_delay_shadow(search_id, route_features)
        ml_tatkal = await shadow.predict_tatkal_shadow(search_id, route_features)

        # Baseline predictions for comparison
        baseline = BaselineHeuristicModels()
        baseline_delay = await baseline.predict_delay_baseline(route_features)
        baseline_tatkal = await baseline.predict_tatkal_baseline(route_features)

        # Log for analysis (could be sent to analytics service)
        shadow_log = {
            "search_id": search_id,
            "ml_delay_prediction": ml_delay,
            "ml_tatkal_prediction": ml_tatkal,
            "baseline_delay_prediction": baseline_delay,
            "baseline_tatkal_prediction": baseline_tatkal,
            "features": route_features,
            "timestamp": datetime.utcnow().isoformat()
        }

        logging.info(f"Shadow inference completed for {search_id}")

    # Return production results only
    return production_results

async def process_route_search(features: Dict[str, Any]) -> Dict[str, Any]:
    """Placeholder for actual route search processing"""
    return {"routes": [], "status": "success"}

if __name__ == "__main__":
    # Example usage
    async def main():
        logging.basicConfig(level=logging.INFO)

        route_features = {
            "search_id": "test_123",
            "origin_station": "NDLS",
            "destination_station": "MMCT",
            "distance_km": 1384,
            "search_hour": 14,
            "search_day_of_week": 2,
            "days_to_travel": 5,
            "is_peak_season": True,
            "avg_price_per_km": 1.5,
            "train_count": 8,
            "has_tatkal_available": True
        }

        # Test shadow inference
        async with ShadowInferenceService(enable_shadow=True) as shadow:
            delay_pred = await shadow.predict_delay_shadow("test_123", route_features)
            tatkal_pred = await shadow.predict_tatkal_shadow("test_123", route_features)

            print(f"Shadow delay prediction: {delay_pred}")
            print(f"Shadow Tatkal prediction: {tatkal_pred}")

        # Test baseline models
        baseline = BaselineHeuristicModels()
        baseline_delay = await baseline.predict_delay_baseline(route_features)
        baseline_tatkal = await baseline.predict_tatkal_baseline(route_features)

        print(f"Baseline delay prediction: {baseline_delay}")
        print(f"Baseline Tatkal prediction: {baseline_tatkal}")

    asyncio.run(main())