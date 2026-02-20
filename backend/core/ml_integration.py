"""
Shared ML Integration Framework

Consolidates ML model loading and inference patterns across:
- pricing/engine.py (TatkalDemandPredictor, RouteRankingPredictor)
- routing/engine.py (RouteRankingModel)
- intelligence/models/ (All ML models)

Features:
- Unified model loading with fallback
- Feature engineering utilities
- Inference pipeline
- Model versioning and registry
- Graceful degradation when models unavailable
"""

import logging
import os
from typing import Dict, Optional, Any, List
from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Metadata for an ML model."""
    model_id: str
    version: str
    created_at: str
    model_type: str  # 'regression', 'classification', 'ranking', etc.
    input_features: List[str]
    output_type: str
    accuracy: Optional[float] = None
    performance_metrics: Dict[str, float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'model_id': self.model_id,
            'version': self.version,
            'created_at': self.created_at,
            'model_type': self.model_type,
            'input_features': self.input_features,
            'output_type': self.output_type,
            'accuracy': self.accuracy,
            'performance_metrics': self.performance_metrics or {},
        }


class MLModel(ABC):
    """
    Abstract base class for all ML models.

    Provides:
    - Standard loading interface
    - Consistent inference API
    - Fallback mechanism
    - Feature validation
    """

    def __init__(self, model_id: str, model_type: str = "unknown"):
        """
        Initialize ML model.

        Args:
            model_id: Unique identifier for model
            model_type: Type of model (regression, classification, ranking, etc.)
        """
        self.model_id = model_id
        self.model_type = model_type
        self.loaded = False
        self.metadata: Optional[ModelMetadata] = None
        self._model = None
        self._last_error: Optional[str] = None

    @abstractmethod
    def load_from_file(self, model_path: Optional[str] = None) -> bool:
        """
        Load model from file.

        Args:
            model_path: Optional path to model file

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def predict(self, features: Dict[str, Any]) -> Any:
        """
        Make a prediction with the model.

        Args:
            features: Input features dictionary

        Returns:
            Prediction result
        """
        pass

    async def predict_with_fallback(self, features: Dict[str, Any], fallback_value: Any) -> Any:
        """
        Make prediction with fallback value if model fails.

        Args:
            features: Input features
            fallback_value: Value to return if prediction fails

        Returns:
            Prediction or fallback value
        """
        if not self.loaded:
            logger.debug(f"Model {self.model_id} not loaded, using fallback")
            return fallback_value

        try:
            return await self.predict(features)
        except Exception as e:
            logger.error(f"Prediction failed for {self.model_id}: {e}")
            self._last_error = str(e)
            return fallback_value

    def get_status(self) -> Dict[str, Any]:
        """Get model status."""
        return {
            'model_id': self.model_id,
            'model_type': self.model_type,
            'loaded': self.loaded,
            'last_error': self._last_error,
            'metadata': self.metadata.to_dict() if self.metadata else None,
        }

    def validate_features(self, features: Dict[str, Any]) -> bool:
        """
        Validate input features match model requirements.

        Args:
            features: Input features to validate

        Returns:
            True if valid, False otherwise
        """
        if not self.metadata:
            return True

        for required_feature in self.metadata.input_features:
            if required_feature not in features:
                logger.warning(f"Missing required feature: {required_feature}")
                return False

        return True


class SimpleMLModel(MLModel):
    """
    Simple ML model implementation for testing/fallback.

    Uses heuristics instead of trained model.
    """

    async def predict(self, features: Dict[str, Any]) -> Any:
        """
        Make prediction using heuristics.

        Args:
            features: Input features

        Returns:
            Heuristic prediction
        """
        # Default: return mean or neutral value
        return 0.5


class HybridMLModel(MLModel):
    """
    Hybrid model that can use trained model or fallback to heuristics.

    Useful when ML model is optional but heuristics can provide reasonable results.
    """

    def __init__(self, model_id: str, model_type: str = "unknown"):
        """Initialize hybrid model."""
        super().__init__(model_id, model_type)
        self._heuristic_fn = None

    def set_heuristic_fallback(self, heuristic_fn):
        """Set fallback heuristic function."""
        self._heuristic_fn = heuristic_fn

    async def predict(self, features: Dict[str, Any]) -> Any:
        """
        Predict using model if loaded, otherwise use heuristic.

        Args:
            features: Input features

        Returns:
            Prediction from model or heuristic
        """
        if self.loaded:
            return await self._predict_with_model(features)
        elif self._heuristic_fn:
            return self._heuristic_fn(features)
        else:
            return 0.5  # Default neutral value

    async def _predict_with_model(self, features: Dict[str, Any]) -> Any:
        """Predict using trained model."""
        # Abstract method to be implemented by subclasses
        raise NotImplementedError("Subclass must implement _predict_with_model")


class MLModelRegistry:
    """
    Registry for all ML models in the system.

    Manages:
    - Model discovery and registration
    - Lazy loading
    - Model switching
    - Monitoring
    """

    def __init__(self):
        """Initialize model registry."""
        self.models: Dict[str, MLModel] = {}
        self._load_errors: Dict[str, str] = {}

    def register_model(self, model: MLModel):
        """Register an ML model."""
        self.models[model.model_id] = model
        logger.info(f"Registered ML model: {model.model_id}")

    def get_model(self, model_id: str) -> Optional[MLModel]:
        """Get a model by ID."""
        return self.models.get(model_id)

    def load_all_models(self):
        """Attempt to load all registered models."""
        logger.info(f"Loading {len(self.models)} registered models...")

        loaded_count = 0
        for model_id, model in self.models.items():
            try:
                if model.load_from_file():
                    loaded_count += 1
                    logger.info(f"✓ Loaded {model_id}")
                else:
                    self._load_errors[model_id] = "Load returned False"
                    logger.warning(f"✗ Failed to load {model_id}")
            except Exception as e:
                self._load_errors[model_id] = str(e)
                logger.error(f"✗ Error loading {model_id}: {e}")

        logger.info(f"Model loading complete: {loaded_count}/{len(self.models)} loaded")

    async def predict(self, model_id: str, features: Dict[str, Any], fallback: Any = None) -> Any:
        """
        Make prediction using a registered model.

        Args:
            model_id: Model identifier
            features: Input features
            fallback: Fallback value if prediction fails

        Returns:
            Prediction or fallback
        """
        model = self.get_model(model_id)
        if not model:
            logger.error(f"Model {model_id} not found in registry")
            return fallback

        return await model.predict_with_fallback(features, fallback)

    def get_registry_status(self) -> Dict[str, Any]:
        """Get status of all models in registry."""
        return {
            'total_models': len(self.models),
            'loaded_models': sum(1 for m in self.models.values() if m.loaded),
            'models': {
                model_id: model.get_status()
                for model_id, model in self.models.items()
            },
            'load_errors': self._load_errors,
        }

    def log_registry_status(self):
        """Log registry status."""
        status = self.get_registry_status()
        logger.info(f"ML Model Registry Status:")
        logger.info(f"  Total Models: {status['total_models']}")
        logger.info(f"  Loaded Models: {status['loaded_models']}")
        for model_id, model_status in status['models'].items():
            symbol = "✓" if model_status['loaded'] else "✗"
            logger.info(f"  {symbol} {model_id}")


# ==============================================================================
# FEATURE ENGINEERING UTILITIES
# ==============================================================================

class FeatureEngineer:
    """
    Utilities for feature engineering and normalization.

    Handles:
    - Feature scaling/normalization
    - Feature combination
    - Feature validation
    """

    @staticmethod
    def normalize_value(value: float, min_val: float, max_val: float) -> float:
        """
        Normalize a value to 0-1 range.

        Args:
            value: Value to normalize
            min_val: Minimum possible value
            max_val: Maximum possible value

        Returns:
            Normalized value (0.0 to 1.0)
        """
        if max_val <= min_val:
            return 0.5

        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))  # Clamp to [0, 1]

    @staticmethod
    def combine_scores(scores: Dict[str, float], weights: Dict[str, float]) -> float:
        """
        Combine multiple scores using weights.

        Args:
            scores: Dictionary of score_name -> value
            weights: Dictionary of score_name -> weight

        Returns:
            Weighted combined score
        """
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(
            scores.get(name, 0.0) * weights.get(name, 0.0)
            for name in scores
        )
        return weighted_sum / total_weight

    @staticmethod
    def create_feature_vector(source: Dict[str, Any], feature_names: List[str]) -> List[float]:
        """
        Extract feature vector from source dictionary.

        Args:
            source: Source data dictionary
            feature_names: Names of features to extract

        Returns:
            Feature vector as list of floats
        """
        return [float(source.get(name, 0.0)) for name in feature_names]


# ==============================================================================
# GLOBAL REGISTRY (SINGLETON)
# ==============================================================================

_global_model_registry: Optional[MLModelRegistry] = None


def get_model_registry() -> MLModelRegistry:
    """Get or create global model registry."""
    global _global_model_registry
    if _global_model_registry is None:
        _global_model_registry = MLModelRegistry()
    return _global_model_registry


def initialize_model_registry():
    """Initialize global model registry."""
    registry = get_model_registry()
    registry.load_all_models()
    return registry
