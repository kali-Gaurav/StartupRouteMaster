import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from backend.config import Config
import logging

logger = logging.getLogger(__name__)

class RouteRankingPredictor:
    """
    ML model to predict P(user_books_this_route) for dynamic route ranking.
    Features: route duration, cost, transfers, predicted_delay, user prefs, time context.
    Target: booking_success from RouteSearchLog.
    """

    def __init__(self):
        self.model = None
        self.model_path = Config.ROUTE_RANKING_MODEL_PATH or "route_ranking_model.pkl"
        self.is_trained = False

    def train_scaffold_model(self):
        """
        Train scaffold model on synthetic data.
        In production, train on real RouteSearchLog data.
        """
        logger.info("Training route ranking scaffold model with synthetic data")

        # Generate synthetic features
        np.random.seed(42)
        n_samples = 10000

        features = {
            'route_duration_hours': np.random.uniform(1, 24, n_samples),
            'route_cost_rupees': np.random.uniform(100, 5000, n_samples),
            'num_transfers': np.random.randint(0, 5, n_samples),
            'predicted_delay_minutes': np.random.uniform(0, 120, n_samples),
            'time_of_day': np.random.randint(0, 24, n_samples),  # hour
            'day_of_week': np.random.randint(0, 7, n_samples),   # 0=Mon, 6=Sun
            'is_weekend': np.random.choice([0, 1], n_samples),
            'user_pref_duration_weight': np.random.uniform(0, 1, n_samples),
            'user_pref_cost_weight': np.random.uniform(0, 1, n_samples),
            'route_popularity_score': np.random.uniform(0, 1, n_samples),  # from historical data
        }

        # Synthetic target: booking probability based on features
        # Lower cost, fewer transfers, less delay -> higher booking prob
        cost_score = 1 / (1 + features['route_cost_rupees'] / 1000)
        duration_score = 1 / (1 + features['route_duration_hours'] / 12)
        transfer_score = 1 / (1 + features['num_transfers'])
        delay_score = 1 / (1 + features['predicted_delay_minutes'] / 60)
        weekend_boost = np.where(features['is_weekend'] == 1, 1.2, 1.0)

        booking_prob = (cost_score * 0.3 + duration_score * 0.3 +
                       transfer_score * 0.2 + delay_score * 0.2) * weekend_boost

        # Add noise and threshold to binary
        noise = np.random.normal(0, 0.1, n_samples)
        booking_prob += noise
        target = (booking_prob > 0.5).astype(int)

        df = pd.DataFrame(features)
        df['booking_success'] = target

        # Train model
        feature_cols = [col for col in df.columns if col != 'booking_success']
        X = df[feature_cols]
        y = df['booking_success']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"Model accuracy: {accuracy:.3f}")
        logger.info(f"Classification report:\n{classification_report(y_test, y_pred)}")

        # Save model
        joblib.dump(self.model, self.model_path)
        self.is_trained = True
        logger.info(f"Model saved to {self.model_path}")

    def predict_booking_probability(self, route_features):
        """
        Predict booking probability for a route.
        route_features: dict with keys matching training features.
        Returns: float probability [0,1]
        """
        if not self.is_trained and self.model is None:
            if not self.load_model():
                logger.warning("Model not trained and cannot load, using default ranking")
                return 0.5  # neutral

        # Ensure features are in the same order as training
        feature_order = ['route_duration_hours', 'route_cost_rupees', 'num_transfers', 
                        'predicted_delay_minutes', 'time_of_day', 'day_of_week', 
                        'is_weekend', 'user_pref_duration_weight', 'user_pref_cost_weight', 
                        'route_popularity_score']
        
        df = pd.DataFrame([route_features])
        df = df[feature_order]  # Reorder columns to match training
        prob = self.model.predict_proba(df)[0][1]  # prob of class 1 (booking)
        return prob

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

    def rank_routes(self, routes, user_prefs=None):
        """
        Rank routes by predicted booking probability.
        routes: list of route dicts with features.
        user_prefs: dict of user preferences (optional).
        Returns: sorted list of routes by descending booking prob.
        """
        if not routes:
            return routes

        ranked_routes = []
        for route in routes:
            features = self.extract_features(route, user_prefs)
            prob = self.predict_booking_probability(features)
            route['booking_probability'] = prob
            ranked_routes.append(route)

        # Sort by booking probability descending
        ranked_routes.sort(key=lambda x: x['booking_probability'], reverse=True)
        return ranked_routes

    def extract_features(self, route, user_prefs=None):
        """
        Extract features from route dict for prediction.
        """
        # Basic route features
        features = {
            'route_duration_hours': route.get('total_duration_minutes', 0) / 60.0,
            'route_cost_rupees': route.get('total_cost', 0),
            'num_transfers': route.get('num_transfers', 0),
            'predicted_delay_minutes': route.get('predicted_delay_minutes', 0),
            'time_of_day': route.get('departure_hour', 12),  # default noon
            'day_of_week': route.get('departure_day_of_week', 0),  # default Monday
            'is_weekend': 1 if route.get('departure_day_of_week', 0) >= 5 else 0,
            'route_popularity_score': route.get('popularity_score', 0.5),  # placeholder
        }

        # User preferences
        if user_prefs:
            features['user_pref_duration_weight'] = user_prefs.get('duration_weight', 0.5)
            features['user_pref_cost_weight'] = user_prefs.get('cost_weight', 0.5)
        else:
            features['user_pref_duration_weight'] = 0.5
            features['user_pref_cost_weight'] = 0.5

        return features

# Global instance
route_ranking_predictor = RouteRankingPredictor()