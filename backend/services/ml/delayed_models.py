"""
ML models for real-time routing intelligence.

Models:
1. DelayPredictionModel - Predict delay at future stations (XGBoost)
2. ReliabilityScoreModel - Predict P(on_time) for train (Gradient Boosting)
3. TransferSuccessProbabilityModel - Predict P(connection_success) (Logistic Regression)

Training uses historical TrainLiveUpdate records as dataset.
Inference runs during routing to score alternatives.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sqlalchemy.orm import Session
import joblib
import pickle

from routemaster_agent.database.models import TrainLiveUpdate, TrainMaster, TrainStation

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Feature extraction from raw train data for ML models.
    """
    
    @staticmethod
    def extract_delay_prediction_features(
        session: Session,
        train_number: str,
        target_station_index: int,
        current_delay: int
    ) -> Optional[pd.DataFrame]:
        """
        Extract features for delay prediction at a specific station.
        
        Features:
        - train_number (categorical)
        - station_index (numeric)
        - current_delay (numeric)
        - time_of_day (hour, minute)
        - day_of_week (0-6)
        - distance_travelled (km)
        - historical_delay_mean (past performance)
        - speed_profile (km/hour)
        
        Args:
            session: Database session
            train_number: Train identifier
            target_station_index: Station to predict for
            current_delay: Current delay in minutes
            
        Returns:
            Feature dataframe or None if insufficient data
        """
        try:
            # Get train info
            train = session.query(TrainMaster).filter(
                TrainMaster.train_number == train_number
            ).first()
            
            if not train:
                return None
            
            # Get station info
            station = session.query(TrainStation).filter(
                TrainStation.train_number == train_number,
                TrainStation.sequence == target_station_index
            ).first()
            
            if not station:
                return None
            
            # Get historical delays for this train
            hist_updates = session.query(TrainLiveUpdate).filter(
                TrainLiveUpdate.train_number == train_number,
                TrainLiveUpdate.recorded_at >= datetime.utcnow() - timedelta(days=30)
            ).all()
            
            if not hist_updates:
                # Use default if no history
                hist_delays = [current_delay]
            else:
                hist_delays = [u.delay_minutes for u in hist_updates]
            
            # Engineer features
            now = datetime.now()
            
            features = {
                'train_number': train_number,
                'station_index': float(target_station_index),
                'current_delay': float(current_delay),
                'hour_of_day': float(now.hour),
                'day_of_week': float(now.weekday()),
                'distance_km': float(station.distance_km or 0),
                'halt_minutes': float(station.halt_minutes or 1),
                'historical_delay_mean': float(np.mean(hist_delays)),
                'historical_delay_std': float(np.std(hist_delays)) if len(hist_delays) > 1 else 0.0,
                'historical_delay_max': float(np.max(hist_delays)),
                'train_type': train.type or 'express',
            }
            
            return pd.DataFrame([features])
        
        except Exception as e:
            logger.error(f"Error extracting delay features: {e}")
            return None
    
    @staticmethod
    def extract_reliability_features(
        session: Session,
        train_number: str,
        days_lookback: int = 30
    ) -> Optional[Dict]:
        """
        Extract features for train reliability scoring.
        
        Features:
        - avg_delay (minutes)
        - delay_variance (minutes²)
        - on_time_percentage (0-100)
        - max_delay_recorded (minutes)
        - frequency_travelling (trips/week)
        - train_type
        
        Args:
            session: Database session
            train_number: Train identifier
            days_lookback: Historical window
            
        Returns:
            Feature dict or None
        """
        try:
            cutoff = datetime.utcnow() - timedelta(days=days_lookback)
            
            updates = session.query(TrainLiveUpdate).filter(
                TrainLiveUpdate.train_number == train_number,
                TrainLiveUpdate.recorded_at >= cutoff
            ).all()
            
            if len(updates) < 10:
                return None  # Insufficient data
            
            delays = [u.delay_minutes for u in updates]
            on_time_count = sum(1 for d in delays if d == 0)
            
            train = session.query(TrainMaster).filter(
                TrainMaster.train_number == train_number
            ).first()
            
            features = {
                'train_number': train_number,
                'avg_delay': float(np.mean(delays)),
                'delay_variance': float(np.var(delays)),
                'on_time_percentage': float(100 * on_time_count / len(delays)),
                'max_delay': float(np.max(delays)),
                'min_delay': float(np.min(delays)),
                'delay_std': float(np.std(delays)),
                'data_points': len(updates),
                'train_type': train.type if train else 'express',
            }
            
            return features
        
        except Exception as e:
            logger.error(f"Error extracting reliability features: {e}")
            return None
    
    @staticmethod
    def extract_transfer_features(
        session: Session,
        arrival_delay: int,
        transfer_buffer_minutes: int,
        source_station_code: str,
        destination_station_code: str
    ) -> Optional[Dict]:
        """
        Extract features for transfer success prediction.
        
        Args:
            session: Database session
            arrival_delay: Arrival delay in minutes
            transfer_buffer_minutes: Planned transfer time
            source_station_code: Source station
            destination_station_code: Destination station
            
        Returns:
            Feature dict or None
        """
        try:
            features = {
                'arrival_delay': float(arrival_delay),
                'transfer_buffer': float(transfer_buffer_minutes),
                'delay_to_buffer_ratio': float(arrival_delay / max(transfer_buffer_minutes, 1)),
                'risk_score': float(arrival_delay / max(transfer_buffer_minutes, 1)),  # >1 = risky
                'buffer_sufficient': 1.0 if arrival_delay <= transfer_buffer_minutes * 0.8 else 0.0,
            }
            
            return features
        
        except Exception as e:
            logger.error(f"Error extracting transfer features: {e}")
            return None


class DelayPredictionModel:
    """
    RandomForest model to predict delay at future stations.
    Trained on historical TrainLiveUpdate data.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'station_index', 'current_delay', 'hour_of_day', 'day_of_week',
            'distance_km', 'halt_minutes', 'historical_delay_mean',
            'historical_delay_std', 'historical_delay_max'
        ]
        
        if model_path:
            self.load(model_path)
    
    def train(
        self,
        session: Session,
        test_size: float = 0.2,
        n_estimators: int = 100
    ) -> Tuple[float, float]:
        """
        Train delay prediction model on historical data.
        
        Args:
            session: Database session
            test_size: Test set fraction
            n_estimators: Random forest parameter
            
        Returns:
            Tuple of (train_r2, test_r2) scores
        """
        logger.info("📚 Training delay prediction model...")
        
        try:
            # Get training data
            updates = session.query(TrainLiveUpdate).filter(
                TrainLiveUpdate.recorded_at >= datetime.utcnow() - timedelta(days=90)
            ).all()
            
            if len(updates) < 100:
                logger.warning("⚠️ Insufficient data for training")
                return 0.0, 0.0
            
            # Extract features and target
            X_list, y_list = [], []
            
            for update in updates:
                features = FeatureEngineer.extract_delay_prediction_features(
                    session,
                    update.train_number,
                    update.sequence,
                    update.delay_minutes
                )
                
                if features is not None:
                    X_list.append(features)
                    y_list.append(update.delay_minutes)
            
            if len(X_list) < 50:
                logger.warning("⚠️ Insufficient feature samples")
                return 0.0, 0.0
            
            X = pd.concat(X_list, ignore_index=True)
            y = np.array(y_list)
            
            # Select numeric features
            X = X[self.feature_columns]
            
            # Split data
            from sklearn.model_selection import train_test_split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42
            )
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            self.model = RandomForestRegressor(
                n_estimators=n_estimators,
                max_depth=20,
                random_state=42,
                n_jobs=-1
            )
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate
            train_r2 = self.model.score(X_train_scaled, y_train)
            test_r2 = self.model.score(X_test_scaled, y_test)
            
            logger.info(f"✓ Model trained: train_r2={train_r2:.3f}, test_r2={test_r2:.3f}")
            
            return train_r2, test_r2
        
        except Exception as e:
            logger.error(f"❌ Training failed: {e}")
            return 0.0, 0.0
    
    def predict(
        self,
        session: Session,
        train_number: str,
        station_index: int,
        current_delay: int
    ) -> Optional[int]:
        """
        Predict delay at target station.
        
        Args:
            session: Database session
            train_number: Train identifier
            station_index: Target station
            current_delay: Current delay
            
        Returns:
            Predicted delay in minutes or None
        """
        if self.model is None:
            logger.warning("Model not trained")
            return current_delay  # Return current as fallback
        
        try:
            features = FeatureEngineer.extract_delay_prediction_features(
                session, train_number, station_index, current_delay
            )
            
            if features is None:
                return current_delay
            
            X = features[self.feature_columns]
            X_scaled = self.scaler.transform(X)
            
            prediction = int(max(0, self.model.predict(X_scaled)[0]))
            
            logger.debug(f"Predicted delay for {train_number}: {prediction}min")
            return prediction
        
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return current_delay


class ReliabilityScoreModel:
    """
    Gradient Boosting model to predict P(train_on_time).
    Scores trains 0-100 for ranking.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'avg_delay', 'delay_variance', 'on_time_percentage',
            'max_delay', 'min_delay', 'delay_std'
        ]
        
        if model_path:
            self.load(model_path)
    
    def train(self, session: Session, n_estimators: int = 50) -> float:
        """
        Train reliability model on historical train performance.
        
        Args:
            session: Database session
            n_estimators: Boosting parameter
            
        Returns:
            Model accuracy score
        """
        logger.info("📚 Training reliability score model...")
        
        try:
            # Get unique trains
            trains = session.query(TrainMaster).all()
            
            if len(trains) < 20:
                logger.warning("⚠️ Insufficient train diversity")
                return 0.0
            
            X_list, y_list = [], []
            
            for train in trains:
                features = FeatureEngineer.extract_reliability_features(
                    session, train.train_number
                )
                
                if features:
                    X_list.append(features)
                    # Create binary target: reliable if on_time_pct > 80%
                    y = 1 if features.get('on_time_percentage', 0) > 80 else 0
                    y_list.append(y)
            
            if len(X_list) < 10:
                logger.warning("⚠️ Insufficient training samples")
                return 0.0
            
            X = pd.DataFrame(X_list)[self.feature_columns]
            y = np.array(y_list)
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train
            self.model = GradientBoostingClassifier(
                n_estimators=n_estimators,
                max_depth=5,
                random_state=42
            )
            self.model.fit(X_scaled, y)
            
            accuracy = self.model.score(X_scaled, y)
            logger.info(f"✓ Reliability model trained: accuracy={accuracy:.3f}")
            
            return accuracy
        
        except Exception as e:
            logger.error(f"❌ Training failed: {e}")
            return 0.0
    
    def get_reliability_score(
        self,
        session: Session,
        train_number: str
    ) -> Optional[float]:
        """
        Get reliability score for a train (0-100).
        
        Args:
            session: Database session
            train_number: Train identifier
            
        Returns:
            Reliability score 0-100 or None
        """
        if self.model is None:
            return 50.0  # Default middle score
        
        try:
            features = FeatureEngineer.extract_reliability_features(
                session, train_number
            )
            
            if features is None:
                return 50.0
            
            X = pd.DataFrame([features])[self.feature_columns]
            X_scaled = self.scaler.transform(X)
            
            # Get probability of being reliable
            prob_reliable = self.model.predict_proba(X_scaled)[0][1]
            score = prob_reliable * 100
            
            logger.debug(f"Reliability score for {train_number}: {score:.1f}")
            return score
        
        except Exception as e:
            logger.error(f"Error calculating reliability score: {e}")
            return 50.0


class TransferSuccessProbabilityModel:
    """
    Logistic Regression model to predict P(connection_success).
    Used for transfer reliability scoring in route ranking.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'arrival_delay', 'transfer_buffer', 'delay_to_buffer_ratio'
        ]
        
        if model_path:
            self.load(model_path)
    
    def get_transfer_success_probability(
        self,
        arrival_delay: int,
        transfer_buffer_minutes: int,
        **kwargs
    ) -> float:
        """
        Estimate probability of successful transfer.
        
        Heuristic model (can be replaced with trained model):
        P(success) = 1 - P(miss)
        
        P(miss) increases with delay and decreases with buffer.
        
        Args:
            arrival_delay: Delay at source station (minutes)
            transfer_buffer_minutes: Available transfer time
            
        Returns:
            Probability 0-1
        """
        if transfer_buffer_minutes <= 0:
            return 0.0
        
        if arrival_delay == 0:
            return 0.95  # 95% success if on time
        
        # Delay-to-buffer ratio
        ratio = arrival_delay / transfer_buffer_minutes
        
        # Sigmoid function to map ratio to probability
        # P(success) = 1 / (1 + exp(ratio * 2))
        # This models: ratio < 0.5 -> high success, ratio > 1.0 -> low success
        prob_miss = 1.0 / (1.0 + np.exp(-ratio * 2 + 1.0))
        prob_success = 1.0 - prob_miss
        
        logger.debug(
            f"Transfer probability: delay={arrival_delay}min, "
            f"buffer={transfer_buffer_minutes}min, P(success)={prob_success:.2f}"
        )
        
        return max(0.0, min(1.0, prob_success))  # Clamp to [0,1]
    
    def save(self, path: str):
        """Save model to disk."""
        with open(path, 'wb') as f:
            pickle.dump((self.model, self.scaler), f)
    
    def load(self, path: str):
        """Load model from disk."""
        with open(path, 'rb') as f:
            self.model, self.scaler = pickle.load(f)


# Convenience module functions
def train_all_models(session: Session) -> Dict[str, float]:
    """
    Train all ML models on current data.
    
    Returns:
        Dict of model_name -> score
    """
    logger.info("=" * 60)
    logger.info("🤖 Training complete ML pipeline...")
    
    results = {}
    
    # Train delay prediction
    delay_model = DelayPredictionModel()
    train_r2, test_r2 = delay_model.train(session)
    results['delay_prediction'] = test_r2
    
    # Train reliability score
    reliability_model = ReliabilityScoreModel()
    accuracy = reliability_model.train(session)
    results['reliability_score'] = accuracy
    
    # Transfer model uses heuristic (no training needed)
    results['transfer_probability'] = 1.0  # Heuristic model always "ready"
    
    logger.info(f"✓ Training complete: {results}")
    logger.info("=" * 60)
    
    return results
