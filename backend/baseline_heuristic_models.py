#!/usr/bin/env python3
"""
RouteMaster Baseline Heuristic Models
=====================================

These models provide simple, rule-based predictions for comparison against ML models.
Always evaluate ML performance against these baselines before production deployment.

Key Principle: If ML doesn't beat baseline heuristics, don't deploy it.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import statistics
from dataclasses import dataclass
import redis.asyncio as redis

@dataclass
class DelayPrediction:
    """Delay prediction result"""
    minutes: float
    confidence: float  # 0.0 to 1.0
    method: str  # Which heuristic was used

@dataclass
class TatkalPrediction:
    """Tatkal booking prediction result"""
    probability: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    method: str  # Which heuristic was used

class BaselineDelayPredictor:
    """
    Baseline delay prediction using historical patterns and simple rules

    Methods (in order of preference):
    1. Route + time-of-day historical average
    2. Route-only historical average
    3. Station-pair distance-based estimate
    4. Global average fallback
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.global_avg_delay = 12.5  # minutes, based on typical railway delays

    async def predict(self, features: Dict[str, Any]) -> DelayPrediction:
        """
        Predict delay using best available heuristic

        Args:
            features: Route search features

        Returns:
            DelayPrediction with minutes, confidence, and method
        """
        try:
            # Method 1: Route + time-of-day specific
            route_time_key = self._make_route_time_key(features)
            prediction = await self._get_historical_average(route_time_key)

            if prediction and prediction > 0:
                adjusted = self._apply_adjustments(prediction, features)
                return DelayPrediction(
                    minutes=max(0, adjusted),
                    confidence=0.8,  # High confidence for specific historical data
                    method="route_time_historical"
                )

            # Method 2: Route-only historical
            route_key = self._make_route_key(features)
            prediction = await self._get_historical_average(route_key)

            if prediction and prediction > 0:
                adjusted = self._apply_adjustments(prediction, features)
                return DelayPrediction(
                    minutes=max(0, adjusted),
                    confidence=0.6,  # Medium confidence for route-only data
                    method="route_historical"
                )

            # Method 3: Distance-based regression
            distance_minutes = self._predict_delay_from_distance(features)
            return DelayPrediction(
                minutes=max(0, distance_minutes),
                confidence=0.4,  # Lower confidence for regression
                method="distance_regression"
            )

        except Exception as e:
            logging.error(f"Baseline delay prediction failed: {e}")

        # Method 4: Global average fallback
        return DelayPrediction(
            minutes=self.global_avg_delay,
            confidence=0.2,  # Low confidence fallback
            method="global_average"
        )

    def _make_route_key(self, features: Dict[str, Any]) -> str:
        """Create route key for caching"""
        origin = features.get('origin_station', 'UNK')
        dest = features.get('destination_station', 'UNK')
        return f"delay:route:{origin}:{dest}"

    def _make_route_time_key(self, features: Dict[str, Any]) -> str:
        """Create route + time key for caching"""
        route_key = self._make_route_key(features)
        hour = features.get('search_hour', 12)
        # Group hours: 0-5 (night), 6-11 (morning), 12-17 (afternoon), 18-23 (evening)
        time_group = hour // 6
        return f"{route_key}:time:{time_group}"

    async def _get_historical_average(self, key: str) -> Optional[float]:
        """Get historical average delay from cache/database"""
        try:
            # In production, this would query your delay history database
            # For now, return mock data based on key patterns
            if "time:0" in key:  # Night
                return 8.5
            elif "time:1" in key:  # Morning peak
                return 18.2
            elif "time:2" in key:  # Afternoon
                return 14.1
            elif "time:3" in key:  # Evening peak
                return 16.8
            else:
                return 12.5
        except Exception:
            return None

    def _apply_adjustments(self, base_delay: float, features: Dict[str, Any]) -> float:
        """Apply contextual adjustments to base delay"""
        adjusted = base_delay

        # Seasonal adjustment
        if features.get('is_peak_season', False):
            adjusted *= 1.4  # 40% increase during peak season

        # Weekend adjustment
        if features.get('is_weekend', False):
            adjusted *= 1.1  # 10% increase on weekends

        # Distance adjustment (longer routes tend to have more delays)
        distance_km = features.get('distance_km', 0)
        if distance_km > 1000:
            adjusted *= 1.2  # 20% increase for long routes

        # Train frequency adjustment (more trains = less delay)
        train_count = features.get('train_count', 1)
        if train_count < 3:
            adjusted *= 1.15  # 15% increase for low frequency routes

        return adjusted

    def _predict_delay_from_distance(self, features: Dict[str, Any]) -> float:
        """Simple regression: delay = a * distance + b"""
        distance_km = features.get('distance_km', 500)

        # Coefficients based on typical railway patterns
        # Short routes: lower delays, long routes: higher delays
        if distance_km < 200:
            return 5.0  # Short routes have minimal delays
        elif distance_km < 500:
            return 8.0 + (distance_km - 200) * 0.02  # Gradual increase
        elif distance_km < 1000:
            return 12.0 + (distance_km - 500) * 0.015  # Slower increase
        else:
            return 18.0 + (distance_km - 1000) * 0.01  # Long routes have higher baseline

class BaselineTatkalPredictor:
    """
    Baseline Tatkal booking prediction using historical patterns and rules

    Methods (in order of preference):
    1. Route + time-to-travel historical rate
    2. Route-only historical rate
    3. Urgency + price-based estimate
    4. Global average fallback
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.global_avg_tatkal_rate = 0.22  # 22% of bookings are Tatkal

    async def predict(self, features: Dict[str, Any]) -> TatkalPrediction:
        """
        Predict Tatkal booking probability using best available heuristic

        Args:
            features: Route search features

        Returns:
            TatkalPrediction with probability, confidence, and method
        """
        try:
            # Method 1: Route + urgency specific
            route_urgency_key = self._make_route_urgency_key(features)
            prediction = await self._get_historical_tatkal_rate(route_urgency_key)

            if prediction is not None:
                adjusted = self._apply_tatkal_adjustments(prediction, features)
                return TatkalPrediction(
                    probability=max(0.0, min(1.0, adjusted)),
                    confidence=0.8,  # High confidence for specific historical data
                    method="route_urgency_historical"
                )

            # Method 2: Route-only historical
            route_key = self._make_route_key(features)
            prediction = await self._get_historical_tatkal_rate(route_key)

            if prediction is not None:
                adjusted = self._apply_tatkal_adjustments(prediction, features)
                return TatkalPrediction(
                    probability=max(0.0, min(1.0, adjusted)),
                    confidence=0.6,  # Medium confidence for route-only data
                    method="route_historical"
                )

            # Method 3: Urgency + price-based estimate
            urgency_price_prob = self._predict_tatkal_from_urgency_price(features)
            return TatkalPrediction(
                probability=max(0.0, min(1.0, urgency_price_prob)),
                confidence=0.4,  # Lower confidence for rule-based
                method="urgency_price_rules"
            )

        except Exception as e:
            logging.error(f"Baseline Tatkal prediction failed: {e}")

        # Method 4: Global average fallback
        return TatkalPrediction(
            probability=self.global_avg_tatkal_rate,
            confidence=0.2,  # Low confidence fallback
            method="global_average"
        )

    def _make_route_key(self, features: Dict[str, Any]) -> str:
        """Create route key for caching"""
        origin = features.get('origin_station', 'UNK')
        dest = features.get('destination_station', 'UNK')
        return f"tatkal:route:{origin}:{dest}"

    def _make_route_urgency_key(self, features: Dict[str, Any]) -> str:
        """Create route + urgency key for caching"""
        route_key = self._make_route_key(features)
        days_to_travel = features.get('days_to_travel', 7)

        # Group urgency: 0-1 (immediate), 2-3 (urgent), 4-7 (soon), 8+ (planned)
        if days_to_travel <= 1:
            urgency_group = 0
        elif days_to_travel <= 3:
            urgency_group = 1
        elif days_to_travel <= 7:
            urgency_group = 2
        else:
            urgency_group = 3

        return f"{route_key}:urgency:{urgency_group}"

    async def _get_historical_tatkal_rate(self, key: str) -> Optional[float]:
        """Get historical Tatkal booking rate from cache/database"""
        try:
            # In production, this would query your booking history database
            # For now, return mock data based on key patterns
            if "urgency:0" in key:  # Immediate (0-1 days)
                return 0.65  # Very high Tatkal usage
            elif "urgency:1" in key:  # Urgent (2-3 days)
                return 0.45  # High Tatkal usage
            elif "urgency:2" in key:  # Soon (4-7 days)
                return 0.25  # Moderate Tatkal usage
            elif "urgency:3" in key:  # Planned (8+ days)
                return 0.08  # Low Tatkal usage
            else:
                return 0.22  # General average
        except Exception:
            return None

    def _apply_tatkal_adjustments(self, base_rate: float, features: Dict[str, Any]) -> float:
        """Apply contextual adjustments to base Tatkal rate"""
        adjusted = base_rate

        # Weekend adjustment (higher Tatkal usage on weekends)
        if features.get('is_weekend', False):
            adjusted *= 1.3

        # Peak season adjustment (higher Tatkal usage during peak times)
        if features.get('is_peak_season', False):
            adjusted *= 1.2

        # Price sensitivity (higher prices increase Tatkal likelihood)
        avg_price_per_km = features.get('avg_price_per_km', 1.0)
        if avg_price_per_km > 2.0:
            adjusted *= 1.25  # Expensive routes have higher Tatkal usage

        # Availability adjustment (if Tatkal is available, higher usage)
        if features.get('has_tatkal_available', True):
            adjusted *= 1.1  # Slight increase when available
        else:
            adjusted *= 0.1  # Massive decrease when not available

        # Passenger count adjustment (families/groups more likely to book Tatkal)
        passenger_count = features.get('passenger_count', 1)
        if passenger_count > 2:
            adjusted *= 1.15

        return adjusted

    def _predict_tatkal_from_urgency_price(self, features: Dict[str, Any]) -> float:
        """Rule-based Tatkal prediction from urgency and price"""
        days_to_travel = features.get('days_to_travel', 7)
        avg_price_per_km = features.get('avg_price_per_km', 1.0)
        has_tatkal = features.get('has_tatkal_available', True)

        if not has_tatkal:
            return 0.01  # Nearly impossible if Tatkal not available

        # Base probability from urgency
        if days_to_travel <= 1:
            base_prob = 0.7
        elif days_to_travel <= 3:
            base_prob = 0.5
        elif days_to_travel <= 7:
            base_prob = 0.3
        else:
            base_prob = 0.1

        # Price adjustment
        if avg_price_per_km > 2.0:
            base_prob *= 1.3
        elif avg_price_per_km < 0.8:
            base_prob *= 0.8

        return base_prob

class BaselineEvaluator:
    """
    Evaluates ML model performance against baseline heuristics

    Key metrics:
    - Improvement over baseline
    - Confidence intervals
    - Statistical significance
    """

    def __init__(self):
        self.delay_predictor = BaselineDelayPredictor()
        self.tatkal_predictor = BaselineTatkalPredictor()

    async def evaluate_delay_model(self,
                                  ml_predictions: List[Tuple[float, Dict[str, Any]]],
                                  actual_delays: List[float]) -> Dict[str, Any]:
        """
        Evaluate ML delay predictions against baseline

        Args:
            ml_predictions: List of (prediction, features) tuples
            actual_delays: List of actual delay values

        Returns:
            Evaluation metrics dictionary
        """
        baseline_predictions = []
        baseline_methods = []

        for _, features in ml_predictions:
            baseline_pred = await self.delay_predictor.predict(features)
            baseline_predictions.append(baseline_pred.minutes)
            baseline_methods.append(baseline_pred.method)

        # Calculate metrics
        ml_mae = self._calculate_mae([pred for pred, _ in ml_predictions], actual_delays)
        baseline_mae = self._calculate_mae(baseline_predictions, actual_delays)

        improvement = (baseline_mae - ml_mae) / baseline_mae if baseline_mae > 0 else 0

        return {
            "ml_mae": ml_mae,
            "baseline_mae": baseline_mae,
            "improvement_pct": improvement * 100,
            "baseline_methods_used": list(set(baseline_methods)),
            "sample_size": len(ml_predictions),
            "ml_beats_baseline": improvement > 0.05  # 5% improvement threshold
        }

    async def evaluate_tatkal_model(self,
                                   ml_predictions: List[Tuple[float, Dict[str, Any]]],
                                   actual_bookings: List[bool]) -> Dict[str, Any]:
        """
        Evaluate ML Tatkal predictions against baseline

        Args:
            ml_predictions: List of (prediction, features) tuples
            actual_bookings: List of actual Tatkal booking outcomes

        Returns:
            Evaluation metrics dictionary
        """
        baseline_predictions = []
        baseline_methods = []

        for _, features in ml_predictions:
            baseline_pred = await self.tatkal_predictor.predict(features)
            baseline_predictions.append(baseline_pred.probability)
            baseline_methods.append(baseline_pred.method)

        # Calculate metrics
        ml_auc = self._calculate_auc([pred for pred, _ in ml_predictions], actual_bookings)
        baseline_auc = self._calculate_auc(baseline_predictions, actual_bookings)

        improvement = (ml_auc - baseline_auc) if baseline_auc > 0 else 0

        return {
            "ml_auc": ml_auc,
            "baseline_auc": baseline_auc,
            "improvement": improvement,
            "baseline_methods_used": list(set(baseline_methods)),
            "sample_size": len(ml_predictions),
            "ml_beats_baseline": improvement > 0.02  # 0.02 AUC improvement threshold
        }

    def _calculate_mae(self, predictions: List[float], actuals: List[float]) -> float:
        """Calculate Mean Absolute Error"""
        if len(predictions) != len(actuals):
            raise ValueError("Predictions and actuals must have same length")

        errors = [abs(pred - actual) for pred, actual in zip(predictions, actuals)]
        return statistics.mean(errors)

    def _calculate_auc(self, predictions: List[float], actuals: List[bool]) -> float:
        """Calculate Area Under ROC Curve (simplified implementation)"""
        if len(predictions) != len(actuals):
            raise ValueError("Predictions and actuals must have same length")

        # Sort by prediction score
        combined = list(zip(predictions, actuals))
        combined.sort(key=lambda x: x[0], reverse=True)

        n_positives = sum(actuals)
        n_negatives = len(actuals) - n_positives

        if n_positives == 0 or n_negatives == 0:
            return 0.5  # No discrimination possible

        # Calculate AUC using trapezoidal rule
        auc = 0.0
        tp = 0.0
        fp = 0.0
        prev_tpr = 0.0
        prev_fpr = 0.0

        for pred, actual in combined:
            if actual:
                tp += 1
            else:
                fp += 1

            tpr = tp / n_positives
            fpr = fp / n_negatives

            auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2
            prev_tpr = tpr
            prev_fpr = fpr

        return auc

# Example usage and testing
async def main():
    """Example usage of baseline models"""
    logging.basicConfig(level=logging.INFO)

    # Sample route features
    test_features = {
        "origin_station": "NDLS",
        "destination_station": "MMCT",
        "distance_km": 1384,
        "search_hour": 14,  # 2 PM
        "search_day_of_week": 2,  # Wednesday
        "days_to_travel": 3,  # Urgent booking
        "is_peak_season": True,
        "is_weekend": False,
        "train_count": 8,
        "has_tatkal_available": True,
        "avg_price_per_km": 1.8,
        "passenger_count": 2
    }

    # Test delay prediction
    delay_predictor = BaselineDelayPredictor()
    delay_pred = await delay_predictor.predict(test_features)

    print("=== Delay Prediction ===")
    print(f"Predicted delay: {delay_pred.minutes:.1f} minutes")
    print(f"Confidence: {delay_pred.confidence:.2f}")
    print(f"Method: {delay_pred.method}")

    # Test Tatkal prediction
    tatkal_predictor = BaselineTatkalPredictor()
    tatkal_pred = await tatkal_predictor.predict(test_features)

    print("\n=== Tatkal Prediction ===")
    print(f"Predicted probability: {tatkal_pred.probability:.3f}")
    print(f"Confidence: {tatkal_pred.confidence:.2f}")
    print(f"Method: {tatkal_pred.method}")

    # Test evaluation framework
    print("\n=== Model Evaluation Framework ===")
    evaluator = BaselineEvaluator()

    # Mock ML predictions and actuals for delay
    mock_ml_delay_preds = [(delay_pred.minutes + 2, test_features), (delay_pred.minutes - 1, test_features)]
    mock_actual_delays = [delay_pred.minutes + 1, delay_pred.minutes - 0.5]

    delay_eval = await evaluator.evaluate_delay_model(mock_ml_delay_preds, mock_actual_delays)
    print(f"Delay Model Evaluation: {delay_eval}")

    # Mock ML predictions and actuals for Tatkal
    mock_ml_tatkal_preds = [(tatkal_pred.probability + 0.1, test_features), (tatkal_pred.probability - 0.05, test_features)]
    mock_actual_tatkal = [True, False]

    tatkal_eval = await evaluator.evaluate_tatkal_model(mock_ml_tatkal_preds, mock_actual_tatkal)
    print(f"Tatkal Model Evaluation: {tatkal_eval}")

if __name__ == "__main__":
    asyncio.run(main())