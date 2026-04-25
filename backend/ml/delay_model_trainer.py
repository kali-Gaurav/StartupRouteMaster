"""
ML Model Training Framework

Implements trainable ML models for predictions:
- Delay prediction
- Cancellation prediction
- Demand forecasting

Features:
- Automated training pipeline
- Model versioning
- Performance monitoring
- Incremental learning
"""

import logging
import os
import pickle
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, accuracy_score, classification_report
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.resilience import circuit_breaker_manager, CircuitConfig

logger = logging.getLogger("ml.trainer")


@dataclass
class ModelMetrics:
    """Model performance metrics"""
    mae: float = 0.0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    training_date: datetime = None
    sample_count: int = 0


@dataclass
class ModelMetadata:
    """Model metadata"""
    model_path: str
    model_type: str
    version: str
    trained_at: datetime
    metrics: ModelMetrics
    feature_names: List[str]
    hyperparameters: Dict[str, Any]


class BaseModelTrainer:
    """Base class for ML model training"""
    
    def __init__(self, db: Session, model_dir: str = "backend/ml/models"):
        self.db = db
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._circuit_breaker = circuit_breaker_manager.get_or_create(
            f"ml_{self.model_type}",
            CircuitConfig(failure_threshold=3, timeout_seconds=300.0, success_threshold=1)
        )
        logger.info(f"{self.model_type} trainer initialized")
    
    async def train(self, days: int = 365) -> ModelMetadata:
        """Train model on historical data"""
        try:
            # Fetch training data
            data = await self._fetch_training_data(days)
            
            if len(data) < 100:
                logger.warning(f"Insufficient training data: {len(data)} samples")
                return None
            
            # Feature engineering
            features, labels = self._extract_features(data)
            
            if len(features) == 0:
                logger.error("No valid features extracted")
                return None
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                features, labels, test_size=0.2, random_state=42
            )
            
            # Train model
            model = self._create_model()
            model.fit(X_train, y_train)
            
            # Evaluate
            metrics = self._evaluate(model, X_test, y_test)
            
            # Save model
            model_path = self._save_model(model, metrics)
            
            # Log training
            logger.info(f"{self.model_type} trained: samples={len(data)}, mae={metrics.mae}")
            
            return ModelMetadata(
                model_path=model_path,
                model_type=self.model_type,
                version=self._generate_version(),
                trained_at=datetime.utcnow(),
                metrics=metrics,
                feature_names=self._get_feature_names(),
                hyperparameters=self._get_hyperparameters(model)
            )
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise
    
    async def predict(self, features: Dict[str, Any]) -> float:
        """Make prediction using trained model"""
        model = self._load_latest_model()
        if not model:
            return self._get_default_prediction()
        
        feature_vector = self._features_to_vector(features)
        return model.predict([feature_vector])[0]
    
    async def batch_predict(self, features_list: List[Dict[str, Any]]) -> List[float]:
        """Make batch predictions"""
        model = self._load_latest_model()
        if not model:
            return [self._get_default_prediction()] * len(features_list)
        
        feature_vectors = [self._features_to_vector(f) for f in features_list]
        return model.predict(feature_vectors).tolist()
    
    def _load_latest_model(self):
        """Load latest trained model"""
        try:
            model_files = list(self.model_dir.glob(f"{self.model_type}_*.pkl"))
            if not model_files:
                return None
            
            latest = max(model_files, key=lambda f: f.stat().st_mtime)
            with open(latest, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return None
    
    def _save_model(self, model, metrics: ModelMetrics) -> str:
        """Save model to disk"""
        version = self._generate_version()
        filename = f"{self.model_type}_{version}.pkl"
        filepath = self.model_dir / filename
        
        with open(filepath, 'wb') as f:
            pickle.dump(model, f)
        
        # Save metadata
        metadata = {
            "version": version,
            "trained_at": datetime.utcnow().isoformat(),
            "metrics": asdict(metrics),
            "feature_names": self._get_feature_names()
        }
        
        metadata_path = self.model_dir / f"{self.model_type}_{version}.json"
        with open(metadata_path, 'w') as f:
            import json
            json.dump(metadata, f, indent=2)
        
        return str(filepath)
    
    def _generate_version(self) -> str:
        """Generate model version"""
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    def _get_default_prediction(self) -> float:
        """Return default prediction when model unavailable"""
        return 0.0
    
    # Abstract methods to implement
    @property
    def model_type(self) -> str:
        raise NotImplementedError
    
    async def _fetch_training_data(self, days: int) -> List[Dict]:
        raise NotImplementedError
    
    def _extract_features(self, data: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError
    
    def _create_model(self):
        raise NotImplementedError
    
    def _evaluate(self, model, X_test, y_test) -> ModelMetrics:
        raise NotImplementedError
    
    def _features_to_vector(self, features: Dict) -> np.ndarray:
        raise NotImplementedError
    
    def _get_feature_names(self) -> List[str]:
        raise NotImplementedError
    
    def _get_hyperparameters(self, model) -> Dict:
        raise NotImplementedError


class DelayModelTrainer(BaseModelTrainer):
    """
    Trains delay prediction model from historical data.
    
    Features:
    - Route-based delay patterns
    - Time-of-day patterns
    - Day-of-week patterns
    - Seasonal patterns
    """
    
    @property
    def model_type(self):
        return "delay_predictor"
    
    async def _fetch_training_data(self, days: int) -> List[Dict]:
        """Fetch historical delay data"""
        from database.models import TrainLiveUpdate
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        updates = self.db.query(TrainLiveUpdate).filter(
            TrainLiveUpdate.timestamp > start_date
        ).all()
        
        data = []
        for update in updates:
            data.append({
                "train_id": update.train_id,
                "station_code": update.station_code,
                "delay_minutes": update.delay_minutes or 0,
                "is_cancelled": update.is_cancelled or False,
                "timestamp": update.timestamp,
                "day_of_week": update.timestamp.weekday(),
                "hour": update.timestamp.hour,
                "month": update.timestamp.month
            })
        
        return data
    
    def _extract_features(self, data: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        """Extract features for delay prediction"""
        features = []
        labels = []
        
        for record in data:
            # Skip cancelled trains for delay prediction
            if record.get("is_cancelled"):
                continue
            
            feature = [
                record.get("train_id", 0) % 100,  # Normalized train ID
                record.get("hour", 12),  # Hour of day
                record.get("day_of_week", 0),  # Day of week
                record.get("month", 1),  # Month
            ]
            
            features.append(feature)
            labels.append(record.get("delay_minutes", 0))
        
        return np.array(features), np.array(labels)
    
    def _create_model(self):
        """Create delay prediction model"""
        return RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
    
    def _evaluate(self, model, X_test, y_test) -> ModelMetrics:
        """Evaluate model performance"""
        predictions = model.predict(X_test)
        mae = mean_absolute_error(y_test, predictions)
        
        return ModelMetrics(
            mae=mae,
            accuracy=0.0,  # Regression, not classification
            training_date=datetime.utcnow(),
            sample_count=len(X_test)
        )
    
    def _features_to_vector(self, features: Dict) -> np.ndarray:
        """Convert feature dict to vector"""
        return np.array([
            features.get("train_id", 0) % 100,
            features.get("hour", 12),
            features.get("day_of_week", 0),
            features.get("month", 1)
        ])
    
    def _get_feature_names(self) -> List[str]:
        return ["train_id_mod", "hour", "day_of_week", "month"]
    
    def _get_hyperparameters(self, model) -> Dict:
        return {
            "n_estimators": model.n_estimators,
            "max_depth": model.max_depth,
            "min_samples_split": model.min_samples_split
        }
    
    def _get_default_prediction(self) -> float:
        return 5.0  # Default 5 minute delay


class CancellationModelTrainer(BaseModelTrainer):
    """
    Trains cancellation prediction model.
    
    Features:
    - User booking patterns
    - Route characteristics
    - Timing factors
    - Historical cancellation rates
    """
    
    @property
    def model_type(self):
        return "cancellation_predictor"
    
    async def _fetch_training_data(self, days: int) -> List[Dict]:
        """Fetch historical booking and cancellation data"""
        from database.models import Booking
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        bookings = self.db.query(Booking).filter(
            Booking.booking_date > start_date
        ).all()
        
        data = []
        for booking in bookings:
            days_before_travel = (booking.travel_date - date.today()).days
            
            data.append({
                "user_id": booking.user_id,
                "route_id": booking.route_id,
                "days_before_travel": days_before_travel,
                "passenger_count": booking.passenger_count,
                "booking_class": booking.booking_class or "SL",
                "is_cancelled": booking.booking_status == "cancelled",
                "booking_hour": booking.booking_date.hour if booking.booking_date else 12,
                "travel_month": booking.travel_date.month
            })
        
        return data
    
    def _extract_features(self, data: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        """Extract features for cancellation prediction"""
        features = []
        labels = []
        
        class_mapping = {"SL": 0, "2S": 1, "3A": 2, "2A": 3, "1A": 4}
        
        for record in data:
            feature = [
                record.get("days_before_travel", 7),
                record.get("passenger_count", 1),
                class_mapping.get(record.get("booking_class", "SL"), 0),
                record.get("booking_hour", 12),
                record.get("travel_month", 1)
            ]
            
            features.append(feature)
            labels.append(1 if record.get("is_cancelled") else 0)
        
        return np.array(features), np.array(labels)
    
    def _create_model(self):
        """Create cancellation prediction model"""
        return GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
    
    def _evaluate(self, model, X_test, y_test) -> ModelMetrics:
        """Evaluate model performance"""
        predictions = model.predict(X_test)
        accuracy = accuracy_score(y_test, predictions)
        
        return ModelMetrics(
            mae=0.0,
            accuracy=accuracy,
            training_date=datetime.utcnow(),
            sample_count=len(X_test)
        )
    
    def _features_to_vector(self, features: Dict) -> np.ndarray:
        """Convert feature dict to vector"""
        class_mapping = {"SL": 0, "2S": 1, "3A": 2, "2A": 3, "1A": 4}
        
        return np.array([
            features.get("days_before_travel", 7),
            features.get("passenger_count", 1),
            class_mapping.get(features.get("booking_class", "SL"), 0),
            features.get("booking_hour", 12),
            features.get("travel_month", 1)
        ])
    
    def _get_feature_names(self) -> List[str]:
        return ["days_before_travel", "passenger_count", "booking_class", "booking_hour", "travel_month"]
    
    def _get_hyperparameters(self, model) -> Dict:
        return {
            "n_estimators": model.n_estimators,
            "max_depth": model.max_depth,
            "learning_rate": model.learning_rate
        }
    
    def _get_default_prediction(self) -> float:
        return 0.1  # 10% default cancellation probability


class DemandModelTrainer(BaseModelTrainer):
    """
    Trains demand forecasting model.
    
    Features:
    - Historical booking patterns
    - Search volume
    - Seasonal factors
    - Event-based spikes
    """
    
    @property
    def model_type(self):
        return "demand_forecaster"
    
    async def _fetch_training_data(self, days: int) -> List[Dict]:
        """Fetch historical demand data"""
        from database.models import Booking, SearchEvent
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get booking counts by route/date
        bookings = self.db.query(
            Booking.source_station,
            Booking.destination_station,
            Booking.travel_date,
            func.count(Booking.id).label("count")
        ).filter(
            Booking.booking_date > start_date
        ).group_by(
            Booking.source_station,
            Booking.destination_station,
            Booking.travel_date
        ).all()
        
        data = []
        for b in bookings:
            # Get search count for same route/date
            searches = self.db.query(func.count(SearchEvent.id)).filter(
                SearchEvent.src == b.source_station,
                SearchEvent.dest == b.destination_station,
                SearchEvent.travel_date == b.travel_date
            ).scalar() or 0
            
            data.append({
                "source": b.source_station,
                "destination": b.destination_station,
                "travel_date": b.travel_date,
                "bookings": b.count,
                "searches": searches,
                "day_of_week": b.travel_date.weekday(),
                "month": b.travel_date.month,
                "days_from_now": (b.travel_date - date.today()).days
            })
        
        return data
    
    def _extract_features(self, data: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        """Extract features for demand prediction"""
        features = []
        labels = []
        
        # Create route encoding
        route_map = {}
        route_id = 0
        for record in data:
            route_key = f"{record['source']}-{record['destination']}"
            if route_key not in route_map:
                route_map[route_key] = route_id
                route_id += 1
        
        for record in data:
            route_key = f"{record['source']}-{record['destination']}"
            
            feature = [
                route_map.get(route_key, 0),
                record.get("day_of_week", 0),
                record.get("month", 1),
                record.get("days_from_now", 7),
                record.get("searches", 0)
            ]
            
            features.append(feature)
            # Target: bookings per search (conversion rate) or raw bookings
            searches = max(1, record.get("searches", 1))
            labels.append(record.get("bookings", 0) / searches)
        
        return np.array(features), np.array(labels)
    
    def _create_model(self):
        """Create demand forecasting model"""
        return RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
    
    def _evaluate(self, model, X_test, y_test) -> ModelMetrics:
        """Evaluate model performance"""
        predictions = model.predict(X_test)
        mae = mean_absolute_error(y_test, predictions)
        
        return ModelMetrics(
            mae=mae,
            accuracy=0.0,
            training_date=datetime.utcnow(),
            sample_count=len(X_test)
        )
    
    def _features_to_vector(self, features: Dict) -> np.ndarray:
        """Convert feature dict to vector"""
        return np.array([
            features.get("route_id", 0),
            features.get("day_of_week", 0),
            features.get("month", 1),
            features.get("days_from_now", 7),
            features.get("searches", 0)
        ])
    
    def _get_feature_names(self) -> List[str]:
        return ["route_id", "day_of_week", "month", "days_from_now", "searches"]
    
    def _get_hyperparameters(self, model) -> Dict:
        return {
            "n_estimators": model.n_estimators,
            "max_depth": model.max_depth
        }
    
    def _get_default_prediction(self) -> float:
        return 0.5  # 50% default demand score


# Model registry and factory
class MLModelRegistry:
    """Registry for trained ML models"""
    
    def __init__(self, db: Session):
        self.db = db
        self.models: Dict[str, BaseModelTrainer] = {}
        self._register_default_models()
    
    def _register_default_models(self):
        """Register default model trainers"""
        self.register("delay", DelayModelTrainer)
        self.register("cancellation", CancellationModelTrainer)
        self.register("demand", DemandModelTrainer)
    
    def register(self, name: str, trainer_class):
        """Register a model trainer"""
        self.models[name] = trainer_class(self.db)
        logger.info(f"Registered model: {name}")
    
    def get_trainer(self, name: str) -> Optional[BaseModelTrainer]:
        """Get model trainer by name"""
        return self.models.get(name)
    
    async def train_all(self, days: int = 365) -> Dict[str, ModelMetadata]:
        """Train all registered models"""
        results = {}
        for name, trainer in self.models.items():
            try:
                metadata = await trainer.train(days)
                if metadata:
                    results[name] = metadata
            except Exception as e:
                logger.error(f"Failed to train {name}: {e}")
        return results
    
    async def predict(self, model_name: str, features: Dict) -> float:
        """Make prediction using specified model"""
        trainer = self.get_trainer(model_name)
        if not trainer:
            logger.error(f"Unknown model: {model_name}")
            return 0.0
        return await trainer.predict(features)


# Global registry
_registry = None

def get_ml_registry(db: Session = None) -> MLModelRegistry:
    """Get or create ML model registry"""
    global _registry
    if _registry is None:
        from database.session import SessionLocal
        db_session = db or SessionLocal()
        _registry = MLModelRegistry(db_session)
    return _registry


# Export for external use
__all__ = [
    'DelayModelTrainer',
    'CancellationModelTrainer',
    'DemandModelTrainer',
    'MLModelRegistry',
    'ModelMetrics',
    'ModelMetadata',
    'get_ml_registry'
]