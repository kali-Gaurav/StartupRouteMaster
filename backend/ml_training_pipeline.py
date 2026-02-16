#!/usr/bin/env python3
"""
RouteMaster ML Training Pipeline
================================

This pipeline processes route search events into ML training datasets.

Architecture:
1. Event Ingestion → Feature Engineering → Dataset Creation → Model Training

Key Components:
- Feature Store: Stores processed features for training/inference
- Training Dataset Builder: Creates labeled datasets from search logs
- Model Trainer: Trains delay prediction and Tatkal models
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge

# Metrics
FEATURE_EXTRACTION_TIME = Histogram('ml_feature_extraction_duration_seconds', 'Time spent extracting features')
DATASET_BUILD_TIME = Histogram('ml_dataset_build_duration_seconds', 'Time spent building training datasets')
MODEL_TRAIN_TIME = Histogram('ml_model_train_duration_seconds', 'Time spent training models')

# Database Models for Feature Store
Base = declarative_base()

class RouteSearchEvent(Base):
    """Raw route search events from Kafka"""
    __tablename__ = 'route_search_events'

    id = Column(Integer, primary_key=True)
    search_id = Column(String(50), unique=True, index=True)
    timestamp = Column(DateTime, index=True)
    user_id = Column(String(50), index=True)
    origin_station = Column(String(10), index=True)
    destination_station = Column(String(10), index=True)
    search_date = Column(DateTime, index=True)
    train_classes = Column(Text)  # JSON array
    passenger_count = Column(Integer)
    raw_request = Column(Text)  # Full request JSON
    raw_response = Column(Text)  # Full response JSON
    processing_time_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class RouteFeatures(Base):
    """Engineered features for ML training"""
    __tablename__ = 'route_features'

    id = Column(Integer, primary_key=True)
    search_id = Column(String(50), unique=True, index=True)
    timestamp = Column(DateTime, index=True)

    # Temporal features
    search_hour = Column(Integer)
    search_day_of_week = Column(Integer)
    days_to_travel = Column(Integer)
    is_weekend = Column(Boolean)
    is_peak_season = Column(Boolean)

    # Route features
    origin_station = Column(String(10), index=True)
    destination_station = Column(String(10), index=True)
    distance_km = Column(Float)
    route_complexity = Column(Float)  # Number of route options

    # Train features
    train_count = Column(Integer)
    avg_duration_minutes = Column(Float)
    has_tatkal_available = Column(Boolean)
    tatkal_slots_available = Column(Integer)

    # Price features
    min_price = Column(Float)
    max_price = Column(Float)
    price_range = Column(Float)
    avg_price_per_km = Column(Float)

    # User context
    passenger_count = Column(Integer)
    preferred_classes = Column(Text)  # JSON array

    # Target variables (populated later)
    actual_delay_minutes = Column(Float, nullable=True)
    tatkal_booked = Column(Boolean, nullable=True)
    booking_confirmed = Column(Boolean, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

class TrainingDataset(Base):
    """Curated training datasets"""
    __tablename__ = 'training_datasets'

    id = Column(Integer, primary_key=True)
    dataset_name = Column(String(100), unique=True)
    version = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Dataset metadata
    record_count = Column(Integer)
    feature_count = Column(Integer)
    date_range_start = Column(DateTime)
    date_range_end = Column(DateTime)
    target_variable = Column(String(50))

    # Data quality metrics
    missing_data_pct = Column(Float)
    duplicate_pct = Column(Float)

    # Storage
    s3_path = Column(String(500))
    local_path = Column(String(500))

class ModelMetadata(Base):
    """Trained model metadata"""
    __tablename__ = 'model_metadata'

    id = Column(Integer, primary_key=True)
    model_name = Column(String(100))
    version = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Model info
    algorithm = Column(String(50))
    hyperparameters = Column(Text)  # JSON
    feature_importance = Column(Text)  # JSON

    # Performance metrics
    train_accuracy = Column(Float)
    validation_accuracy = Column(Float)
    test_accuracy = Column(Float)

    # Deployment
    s3_path = Column(String(500))
    is_active = Column(Boolean, default=False)

class MLTrainingPipeline:
    """Main ML training pipeline orchestrator"""

    def __init__(self, db_url: str, redis_url: str, data_collection_only: bool = True):
        self.engine = create_engine(db_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.redis = redis.from_url(redis_url)
        self.data_collection_only = data_collection_only

        # Create tables
        Base.metadata.create_all(bind=self.engine)

    @FEATURE_EXTRACTION_TIME.time()
    async def extract_features(self, search_event: Dict) -> Dict:
        """Extract features from raw search event"""
        # Parse event data
        search_id = search_event['search_id']
        timestamp = datetime.fromisoformat(search_event['timestamp'])

        # Temporal features
        features = {
            'search_id': search_id,
            'timestamp': timestamp,
            'search_hour': timestamp.hour,
            'search_day_of_week': timestamp.weekday(),
            'days_to_travel': (search_event['search_date'] - timestamp.date()).days,
            'is_weekend': timestamp.weekday() >= 5,
            'is_peak_season': self._is_peak_season(timestamp),
        }

        # Route features
        route_data = search_event['route_data']
        features.update({
            'origin_station': route_data['origin'],
            'destination_station': route_data['destination'],
            'distance_km': route_data.get('distance_km', 0),
            'route_complexity': len(route_data.get('trains', [])),
        })

        # Train features
        trains = route_data.get('trains', [])
        features.update({
            'train_count': len(trains),
            'avg_duration_minutes': np.mean([t.get('duration_minutes', 0) for t in trains]) if trains else 0,
            'has_tatkal_available': any(t.get('tatkal_available', False) for t in trains),
            'tatkal_slots_available': sum(t.get('tatkal_slots', 0) for t in trains),
        })

        # Price features
        prices = [t.get('price', 0) for t in trains if t.get('price')]
        if prices:
            features.update({
                'min_price': min(prices),
                'max_price': max(prices),
                'price_range': max(prices) - min(prices),
                'avg_price_per_km': np.mean(prices) / max(features['distance_km'], 1),
            })

        # User context
        features.update({
            'passenger_count': search_event.get('passenger_count', 1),
            'preferred_classes': json.dumps(search_event.get('preferred_classes', [])),
        })

        return features

    @DATASET_BUILD_TIME.time()
    async def build_training_dataset(self,
                                   target_variable: str,
                                   days_back: int = 30,
                                   min_samples: int = 1000) -> str:
        """Build training dataset for specific target variable"""

        session = self.SessionLocal()

        try:
            # Query features with target labels
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            query = session.query(RouteFeatures).filter(
                RouteFeatures.timestamp >= cutoff_date,
                getattr(RouteFeatures, target_variable).isnot(None)
            )

            features_df = pd.read_sql(query.statement, session.bind)

            if len(features_df) < min_samples:
                raise ValueError(f"Insufficient samples: {len(features_df)} < {min_samples}")

            # Data quality checks
            missing_pct = features_df.isnull().mean().mean()
            duplicate_pct = features_df.duplicated(subset=['search_id']).mean()

            # Create dataset metadata
            dataset_name = f"{target_variable}_v{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            dataset = TrainingDataset(
                dataset_name=dataset_name,
                version=datetime.utcnow().strftime('%Y.%m.%d'),
                record_count=len(features_df),
                feature_count=len(features_df.columns) - 3,  # Exclude id, search_id, created_at
                date_range_start=features_df['timestamp'].min(),
                date_range_end=features_df['timestamp'].max(),
                target_variable=target_variable,
                missing_data_pct=missing_pct,
                duplicate_pct=duplicate_pct,
            )

            session.add(dataset)
            session.commit()

            # Save dataset to storage
            local_path = f"/tmp/{dataset_name}.parquet"
            features_df.to_parquet(local_path)

            # Update storage path
            dataset.local_path = local_path
            session.commit()

            return dataset_name

        finally:
            session.close()

    @MODEL_TRAIN_TIME.time()
    async def train_model(self,
                         dataset_name: str,
                         target_variable: str,
                         algorithm: str = 'xgboost') -> str:
        """Train ML model on dataset"""

        session = self.SessionLocal()

        try:
            # Load dataset
            dataset = session.query(TrainingDataset).filter_by(dataset_name=dataset_name).first()
            if not dataset:
                raise ValueError(f"Dataset {dataset_name} not found")

            # Load features
            features_df = pd.read_parquet(dataset.local_path)

            # Prepare training data
            feature_cols = [col for col in features_df.columns
                          if col not in ['id', 'search_id', 'timestamp', 'created_at', target_variable]]

            X = features_df[feature_cols]
            y = features_df[target_variable]

            # Train model (simplified - would use actual ML framework)
            if algorithm == 'xgboost':
                model = self._train_xgboost(X, y)
            elif algorithm == 'lightgbm':
                model = self._train_lightgbm(X, y)
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")

            # Evaluate model
            train_acc, val_acc, test_acc = self._evaluate_model(model, X, y)

            # Save model metadata
            model_name = f"{target_variable}_{algorithm}_v{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            model_metadata = ModelMetadata(
                model_name=model_name,
                version=datetime.utcnow().strftime('%Y.%m.%d'),
                algorithm=algorithm,
                hyperparameters=json.dumps(model.get_params() if hasattr(model, 'get_params') else {}),
                train_accuracy=train_acc,
                validation_accuracy=val_acc,
                test_accuracy=test_acc,
                is_active=False
            )

            session.add(model_metadata)
            session.commit()

            # Save model artifact
            model_path = f"/tmp/{model_name}.pkl"
            self._save_model(model, model_path)

            model_metadata.local_path = model_path
            session.commit()

            return model_name

        finally:
            session.close()

    def _is_peak_season(self, date: datetime) -> bool:
        """Check if date is in peak season"""
        month = date.month
        # Peak seasons: Summer (May-Jun), Festival (Oct-Nov), Winter (Dec-Jan)
        return month in [5, 6, 10, 11, 12, 1]

    def _train_xgboost(self, X, y):
        """Train XGBoost model (placeholder)"""
        # Would use actual xgboost library
        return {"model_type": "xgboost", "params": {"n_estimators": 100}}

    def _train_lightgbm(self, X, y):
        """Train LightGBM model (placeholder)"""
        # Would use actual lightgbm library
        return {"model_type": "lightgbm", "params": {"n_estimators": 100}}

    def _evaluate_model(self, model, X, y) -> Tuple[float, float, float]:
        """Evaluate model performance (placeholder)"""
        # Would perform actual train/val/test split and evaluation
        return 0.85, 0.82, 0.80

    async def run_data_quality_checks(self) -> Dict[str, float]:
        """Run data quality checks on the feature store"""
        session = self.SessionLocal()

        try:
            # Check total records
            result = session.execute(text("""
                SELECT COUNT(*) as total_records FROM route_features
            """))
            total_records = result.fetchone()[0]

            # Check missing features rate
            result = session.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN search_hour IS NULL THEN 1 END) as missing_hour,
                    COUNT(CASE WHEN distance_km IS NULL THEN 1 END) as missing_distance,
                    COUNT(CASE WHEN train_count IS NULL THEN 1 END) as missing_train_count
                FROM route_features
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
            """))
            row = result.fetchone()
            total_recent = row[0]
            missing_features = sum(row[1:]) if total_recent > 0 else 0
            missing_feature_rate = missing_features / (total_recent * 3) if total_recent > 0 else 0

            # Check label availability
            result = session.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN actual_delay_minutes IS NOT NULL THEN 1 END) as delay_labels,
                    COUNT(CASE WHEN tatkal_booked IS NOT NULL THEN 1 END) as tatkal_labels,
                    COUNT(CASE WHEN booking_confirmed IS NOT NULL THEN 1 END) as booking_labels
                FROM route_features
                WHERE timestamp >= NOW() - INTERVAL '7 days'
            """))
            row = result.fetchone()
            total_week = row[0]
            label_rates = {
                'delay_label_rate': row[1] / total_week if total_week > 0 else 0,
                'tatkal_label_rate': row[2] / total_week if total_week > 0 else 0,
                'booking_label_rate': row[3] / total_week if total_week > 0 else 0,
            }

            # Update Prometheus metrics
            from backend.utils.metrics import (
                ML_MISSING_FEATURE_RATE, ML_DATASET_RECORD_COUNT,
                ML_DATASET_MISSING_LABEL_RATE
            )

            ML_MISSING_FEATURE_RATE.set(missing_feature_rate)
            ML_DATASET_RECORD_COUNT.labels(table_name='route_features').set(total_records)

            for target, rate in label_rates.items():
                ML_DATASET_MISSING_LABEL_RATE.labels(target_variable=target.replace('_rate', '')).set(1 - rate)

            return {
                'total_records': total_records,
                'missing_feature_rate': missing_feature_rate,
                'label_rates': label_rates,
                'data_collection_days': self._calculate_data_collection_days()
            }

        finally:
            session.close()

    def _calculate_data_collection_days(self) -> int:
        """Calculate how many days of data we have"""
        session = self.SessionLocal()
        try:
            result = session.execute(text("""
                SELECT EXTRACT(EPOCH FROM (NOW() - MIN(timestamp))) / 86400 as days
                FROM route_features
            """))
            days = result.fetchone()[0]
            return int(days) if days else 0
        finally:
            session.close()

async def main():
    """Main pipeline execution"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Configuration
    db_url = os.getenv('DATABASE_URL', 'postgresql://routemaster:routemaster@localhost/routemaster_ml')
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

    # Start in data collection mode only
    data_collection_only = os.getenv('ML_DATA_COLLECTION_ONLY', 'true').lower() == 'true'

    pipeline = MLTrainingPipeline(db_url, redis_url, data_collection_only=data_collection_only)

    try:
        logger.info("🧠 RouteMaster ML Pipeline Starting")
        logger.info(f"Data Collection Mode: {data_collection_only}")

        # Always run data quality checks
        logger.info("📊 Running data quality checks...")
        quality_metrics = await pipeline.run_data_quality_checks()

        logger.info("📈 Data Quality Report:")
        logger.info(f"   Total Records: {quality_metrics['total_records']:,}")
        logger.info(f"   Data Collection Days: {quality_metrics['data_collection_days']}")
        logger.info(f"   Missing Feature Rate: {quality_metrics['missing_feature_rate']:.3f}")
        logger.info("   Label Availability:")
        for label, rate in quality_metrics['label_rates'].items():
            logger.info(f"     {label}: {rate:.3f}")

        if data_collection_only:
            logger.info("✅ Data collection mode active - no model training")
            logger.info("💡 Next steps after 30 days of data:")
            logger.info("   1. Set ML_DATA_COLLECTION_ONLY=false")
            logger.info("   2. Run offline training validation")
            logger.info("   3. Deploy models in shadow mode")
            return

        # Model training phase (only if not in data collection mode)
        logger.info("🤖 Starting model training phase...")

        # Build delay prediction dataset
        logger.info("Building delay prediction dataset...")
        delay_dataset = await pipeline.build_training_dataset(
            target_variable='actual_delay_minutes',
            days_back=30,
            min_samples=5000
        )
        logger.info(f"Created dataset: {delay_dataset}")

        # Train delay prediction model
        logger.info("Training delay prediction model...")
        delay_model = await pipeline.train_model(
            delay_dataset,
            'actual_delay_minutes',
            algorithm='xgboost'
        )
        logger.info(f"Trained model: {delay_model}")

        # Build Tatkal booking dataset
        logger.info("Building Tatkal booking dataset...")
        tatkal_dataset = await pipeline.build_training_dataset(
            target_variable='tatkal_booked',
            days_back=30,
            min_samples=2000
        )
        logger.info(f"Created dataset: {tatkal_dataset}")

        # Train Tatkal model
        logger.info("Training Tatkal booking model...")
        tatkal_model = await pipeline.train_model(
            tatkal_dataset,
            'tatkal_booked',
            algorithm='lightgbm'
        )
        logger.info(f"Trained model: {tatkal_model}")

        logger.info("🎉 ML training pipeline completed successfully!")

    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())