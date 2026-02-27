import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from config import Config
import logging

logger = logging.getLogger(__name__)

class TatkalDemandPredictor:
    """
    ML model to predict seat sellout probability for Tatkal booking windows.
    Features: booking velocity, route popularity, seasonality, time to departure, etc.
    Target: sellout_probability [0,1]
    """

    def __init__(self):
        self.model = None
        self.model_path = Config.TATKAL_DEMAND_MODEL_PATH or "tatkal_demand_model.pkl"
        self.is_trained = False

    def train_scaffold_model(self):
        """
        Train scaffold model on synthetic data.
        In production, train on real booking data.
        """
        logger.info("Training Tatkal demand scaffold model with synthetic data")

        # Generate synthetic features
        np.random.seed(42)
        n_samples = 5000

        features = {
            'hours_to_departure': np.random.uniform(1, 168, n_samples),  # 1 hour to 1 week
            'booking_velocity_last_24h': np.random.uniform(0, 100, n_samples),  # bookings per day
            'route_popularity_score': np.random.uniform(0, 1, n_samples),
            'seasonality_factor': np.random.uniform(0.5, 1.5, n_samples),  # peak/off-peak
            'day_of_week': np.random.randint(0, 7, n_samples),
            'month': np.random.randint(1, 13, n_samples),
            'is_holiday_season': np.random.choice([0, 1], n_samples, p=[0.8, 0.2]),
            'current_occupancy_rate': np.random.uniform(0, 1, n_samples),
            'price_premium': np.random.uniform(1, 3, n_samples),  # Tatkal price multiplier
            'competition_factor': np.random.uniform(0.5, 1.5, n_samples),  # other trains available
        }

        # Synthetic target: sellout probability
        # Higher velocity, popularity, closer to departure -> higher sellout prob
        base_prob = (
            (168 - features['hours_to_departure']) / 168 * 0.4 +  # urgency
            features['booking_velocity_last_24h'] / 100 * 0.3 +   # velocity
            features['route_popularity_score'] * 0.2 +            # popularity
            features['seasonality_factor'] / 1.5 * 0.1            # seasonality
        )

        # Add holiday boost and occupancy
        holiday_boost = np.where(features['is_holiday_season'] == 1, 1.3, 1.0)
        occupancy_boost = features['current_occupancy_rate'] * 0.5

        sellout_prob = np.clip(base_prob * holiday_boost + occupancy_boost, 0, 1)

        # Add noise
        noise = np.random.normal(0, 0.1, n_samples)
        sellout_prob = np.clip(sellout_prob + noise, 0, 1)

        df = pd.DataFrame(features)
        df['sellout_probability'] = sellout_prob

        # Train model
        feature_cols = [col for col in df.columns if col != 'sellout_probability']
        X = df[feature_cols]
        y = df['sellout_probability']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        logger.info(f"Model MAE: {mae:.3f}, R²: {r2:.3f}")

        # Save model
        joblib.dump(self.model, self.model_path)
        self.is_trained = True
        logger.info(f"Model saved to {self.model_path}")

    def predict_sellout_probability(self, features):
        """
        Predict sellout probability for Tatkal window.
        features: dict with keys matching training features.
        Returns: float probability [0,1]
        """
        if not self.is_trained and self.model is None:
            if not self.load_model():
                logger.warning("Model not trained and cannot load, using default")
                return 0.5  # neutral

        df = pd.DataFrame([features])
        prob = self.model.predict(df)[0]
        return np.clip(prob, 0, 1)

    def load_model(self):
        """Load trained model from disk."""
        try:
            self.model = joblib.load(self.model_path)
            self.is_trained = True
            logger.info(f"Model loaded from {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def get_tatkal_recommendation(self, route_info, current_time):
        """
        Get Tatkal booking recommendation for a route.
        route_info: dict with route details
        current_time: datetime of booking request
        Returns: dict with sellout_prob, urgency_level, recommended_action
        """
        # Extract features from route_info
        features = self.extract_features(route_info, current_time)

        sellout_prob = self.predict_sellout_probability(features)

        # Determine urgency and recommendation
        if sellout_prob > 0.8:
            urgency = "critical"
            action = "Book immediately - high sellout risk"
        elif sellout_prob > 0.6:
            urgency = "high"
            action = "Book soon - moderate sellout risk"
        elif sellout_prob > 0.4:
            urgency = "medium"
            action = "Monitor and book when convenient"
        else:
            urgency = "low"
            action = "No rush - low sellout risk"

        return {
            'sellout_probability': sellout_prob,
            'urgency_level': urgency,
            'recommended_action': action,
            'tatkal_window_hours': 24,  # Standard Tatkal window
            'features_used': features
        }

    def extract_features(self, route_info, current_time):
        """
        Extract features from route info for prediction.
        """
        # Calculate hours to departure
        departure_time = route_info.get('departure_datetime')
        if departure_time:
            hours_to_dep = (departure_time - current_time).total_seconds() / 3600
        else:
            hours_to_dep = 48  # default 2 days

        return {
            'hours_to_departure': max(1, hours_to_dep),
            'booking_velocity_last_24h': route_info.get('booking_velocity_24h', 10),
            'route_popularity_score': route_info.get('popularity_score', 0.5),
            'seasonality_factor': self._calculate_seasonality(current_time),
            'day_of_week': current_time.weekday(),
            'month': current_time.month,
            'is_holiday_season': 1 if current_time.month in [10, 11, 12, 1] else 0,  # Festival season
            'current_occupancy_rate': route_info.get('current_occupancy', 0.3),
            'price_premium': route_info.get('tatkal_premium', 1.5),
            'competition_factor': route_info.get('competition_score', 1.0),
        }

    def _calculate_seasonality(self, dt):
        """Calculate seasonality factor based on month and day."""
        month = dt.month
        # Peak season: summer vacation (May-Jun), festival season (Oct-Dec)
        if month in [5, 6, 10, 11, 12]:
            return 1.3
        # Shoulder season: Mar-Apr, Sep
        elif month in [3, 4, 9]:
            return 1.1
        # Off season: Jan-Feb, Jul-Aug
        else:
            return 0.8

# Global instance
tatkal_demand_predictor = TatkalDemandPredictor()
