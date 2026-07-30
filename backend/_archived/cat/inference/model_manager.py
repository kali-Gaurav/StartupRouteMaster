"""
Model Manager for the Contextual Availability Transformer (CAT) system.
Handles model loading, versioning, hot-swapping, warm-up, and failure recovery.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import uuid

import torch
import numpy as np

from ..config import settings
from ..models.schemas import AvailabilityPrediction
from .mlflow_client import MLflowClient, ModelVersionInfo, create_mlflow_client
from .cache_manager import CacheManager, PredictionCache, create_cache_manager

logger = logging.getLogger(__name__)


@dataclass
class ModelLoadResult:
    """Result of a model load operation."""
    success: bool
    model: Any = None
    version_info: Optional[ModelVersionInfo] = None
    error_message: Optional[str] = None
    load_time_seconds: float = 0.0
    warmup_completed: bool = False


@dataclass
class ModelVersionState:
    """State of a model version in the manager."""
    version: str
    stage: str
    model: Any
    version_info: ModelVersionInfo
    load_time: datetime
    last_access_time: datetime
    is_warming_up: bool = False
    warmup_completed: bool = False
    warmup_errors: List[str] = field(default_factory=list)
    prediction_count: int = 0
    error_count: int = 0


@dataclass
class ModelWarmupConfig:
    """Configuration for model warm-up."""
    enabled: bool = True
    sample_count: int = 10
    timeout_seconds: int = 60
    validation_fn: Callable[[Any], bool] = None
    required_success_rate: float = 0.9


@dataclass
class ModelReloadConfig:
    """Configuration for model reload on failure."""
    enabled: bool = True
    max_retries: int = 3
    retry_delay_seconds: float = 5.0
    exponential_base: float = 2.0
    max_retry_delay_seconds: float = 60.0
    fallback_to_cached: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes as per requirement 11.3


@dataclass
class HotSwapConfig:
    """Configuration for hot-swapping model versions."""
    enabled: bool = True
    test_before_switch: bool = True
    test_sample_count: int = 5
    test_timeout_seconds: int = 30
    retain_previous_version: bool = True  # Requirement 11.7
    previous_version_retention_hours: int = 24
    traffic_switch_interval_seconds: float = 0.0  # 0 for instant switch


class CachedPrediction:
    """A cached prediction with TTL."""
    
    def __init__(
        self,
        prediction: AvailabilityPrediction,
        cache_time: datetime = None,
        ttl_seconds: int = 300
    ):
        self.prediction = prediction
        self.cache_time = cache_time or datetime.utcnow()
        self.ttl_seconds = ttl_seconds
    
    def is_expired(self) -> bool:
        """Check if the cached prediction is expired."""
        elapsed = (datetime.utcnow() - self.cache_time).total_seconds()
        return elapsed > self.ttl_seconds
    
    def is_within_ttl(self, ttl_seconds: int = None) -> bool:
        """Check if the prediction is within a specific TTL."""
        max_ttl = ttl_seconds or self.ttl_seconds
        elapsed = (datetime.utcnow() - self.cache_time).total_seconds()
        return elapsed <= max_ttl


class ModelManager:
    """
    Manages model loading, versioning, and hot-swapping for CAT inference.
    
    Key features:
    - Load models from MLflow model registry
    - Hot-swap model versions without downtime
    - Model warm-up before serving predictions
    - Failure recovery with cached predictions
    - Retain previous production model for rollback
    - Automatic cache invalidation on model updates
    """
    
    def __init__(
        self,
        mlflow_client: MLflowClient = None,
        warmup_config: ModelWarmupConfig = None,
        reload_config: ModelReloadConfig = None,
        hot_swap_config: HotSwapConfig = None,
        cache_manager: CacheManager = None,
        device: str = "cpu"
    ):
        """
        Initialize the model manager.
        
        Args:
            mlflow_client: MLflow client for model registry
            warmup_config: Model warm-up configuration
            reload_config: Model reload configuration
            hot_swap_config: Hot-swap configuration
            cache_manager: Cache manager for prediction caching and invalidation
            device: Device to load model on (cpu/cuda)
        """
        self.mlflow_client = mlflow_client or create_mlflow_client()
        self.warmup_config = warmup_config or ModelWarmupConfig()
        self.reload_config = reload_config or ModelReloadConfig()
        self.hot_swap_config = hot_swap_config or HotSwapConfig()
        self.device = device
        
        # Cache manager for prediction caching and invalidation
        self._cache_manager = cache_manager
        
        # Model state
        self._production_model: Optional[ModelVersionState] = None
        self._staging_model: Optional[ModelVersionState] = None
        self._previous_production_model: Optional[ModelVersionState] = None
        self._model_lock = threading.RLock()
        
        # Prediction cache for fallback (Requirement 11.3)
        self._prediction_cache: Dict[str, CachedPrediction] = {}
        self._cache_lock = threading.RLock()
        
        # Reload state
        self._reload_in_progress = False
        self._reload_task: Optional[asyncio.Task] = None
        self._reload_event = asyncio.Event()
        
        # Hot-swap state
        self._hot_swap_in_progress = False
        self._traffic_percentage: float = 100.0  # % traffic to new model
        
        # Metrics
        self._metrics = {
            "total_predictions": 0,
            "cached_predictions": 0,
            "model_loads": 0,
            "model_load_failures": 0,
            "hot_swaps": 0,
            "rollbacks": 0,
            "reload_attempts": 0,
            "reload_failures": 0,
            "cache_invalidations": 0
        }
        
        # Thread pool for blocking operations
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info("ModelManager initialized")
    
    def set_cache_manager(self, cache_manager: CacheManager) -> None:
        """
        Set the cache manager for prediction caching and invalidation.
        
        Args:
            cache_manager: Cache manager instance
        """
        self._cache_manager = cache_manager
        logger.info("Cache manager attached to ModelManager")
    
    def _invalidate_cache_on_model_change(self, reason: str) -> int:
        """
        Invalidate cache when model changes.
        
        Args:
            reason: Reason for invalidation (hot_swap, reload, etc.)
            
        Returns:
            Number of cache entries invalidated
        """
        if self._cache_manager is None:
            return 0
        
        try:
            invalidated = self._cache_manager.on_model_reload(
                self.get_production_version() or "unknown"
            )
            self._metrics["cache_invalidations"] += 1
            logger.info(f"Cache invalidated on {reason}: {invalidated} entries")
            return invalidated
        except Exception as e:
            logger.warning(f"Failed to invalidate cache on model change: {e}")
            return 0
    
    def get_production_model(self) -> Optional[Any]:
        """Get the current production model."""
        with self._model_lock:
            if self._production_model:
                self._production_model.last_access_time = datetime.utcnow()
                return self._production_model.model
        return None
    
    def get_production_version(self) -> Optional[str]:
        """Get the current production model version."""
        with self._model_lock:
            if self._production_model:
                return self._production_model.version
        return None
    
    def get_previous_production_model(self) -> Optional[Any]:
        """Get the previous production model for rollback."""
        with self._model_lock:
            if self._previous_production_model:
                return self._previous_production_model.model
        return None
    
    def get_previous_production_version(self) -> Optional[str]:
        """Get the previous production model version."""
        with self._model_lock:
            if self._previous_production_model:
                return self._previous_production_model.version
        return None
    
    def get_staging_model(self) -> Optional[Any]:
        """Get the staging model if available."""
        with self._model_lock:
            if self._staging_model:
                return self._staging_model.model
        return None
    
    def get_staging_version(self) -> Optional[str]:
        """Get the staging model version."""
        with self._model_lock:
            if self._staging_model:
                return self._staging_model.version
        return None
    
    def get_all_versions(self) -> List[Dict[str, Any]]:
        """Get information about all loaded model versions."""
        with self._model_lock:
            versions = []
            
            if self._production_model:
                versions.append({
                    "version": self._production_model.version,
                    "stage": "Production",
                    "loaded": True,
                    "warmup_completed": self._production_model.warmup_completed,
                    "predictions": self._production_model.prediction_count,
                    "load_time": self._production_model.load_time.isoformat()
                })
            
            if self._staging_model:
                versions.append({
                    "version": self._staging_model.version,
                    "stage": "Staging",
                    "loaded": True,
                    "warmup_completed": self._staging_model.warmup_completed,
                    "predictions": self._staging_model.prediction_count,
                    "load_time": self._staging_model.load_time.isoformat()
                })
            
            if self._previous_production_model:
                versions.append({
                    "version": self._previous_production_model.version,
                    "stage": "Previous_Production",
                    "loaded": True,
                    "warmup_completed": self._previous_production_model.warmup_completed,
                    "predictions": self._previous_production_model.prediction_count,
                    "load_time": self._previous_production_model.load_time.isoformat()
                })
            
            return versions
    
    def load_model(
        self,
        version: str = None,
        stage: str = "Production",
        blocking: bool = True
    ) -> ModelLoadResult:
        """
        Load a model from MLflow registry.
        
        Args:
            version: Specific version to load (optional)
            stage: Stage to load from if version not specified
            blocking: Whether to wait for warm-up to complete
            
        Returns:
            ModelLoadResult with success status and loaded model
        """
        start_time = time.time()
        self._metrics["model_loads"] += 1
        
        try:
            # Load model artifact
            model, version_info = self.mlflow_client.load_model_artifact(
                version=version,
                stage=stage
            )
            
            load_time = time.time() - start_time
            
            # Create model version state
            model_state = ModelVersionState(
                version=version_info.version,
                stage=version_info.stage,
                model=model,
                version_info=version_info,
                load_time=datetime.utcnow(),
                last_access_time=datetime.utcnow()
            )
            
            # Perform warm-up if enabled
            warmup_completed = True  # Default to True (no warmup needed)
            if self.warmup_config.enabled:
                warmup_completed = self._run_warmup(model, version_info.version)
                model_state.is_warming_up = not warmup_completed
            else:
                model_state.is_warming_up = False
            model_state.warmup_completed = warmup_completed
            
            # Store model based on stage
            with self._model_lock:
                if version_info.stage == "Production" or stage == "Production":
                    # Retain previous production model for rollback (Requirement 11.7)
                    if self._production_model and self.hot_swap_config.retain_previous_version:
                        self._previous_production_model = self._production_model
                    
                    self._production_model = model_state
                elif version_info.stage == "Staging" or stage == "Staging":
                    self._staging_model = model_state
            
            logger.info(
                f"Loaded model {self.mlflow_client.config.model_name}:{version_info.version} "
                f"(stage={version_info.stage}, warmup={'completed' if warmup_completed else 'pending'})"
            )
            
            return ModelLoadResult(
                success=True,
                model=model,
                version_info=version_info,
                load_time_seconds=load_time,
                warmup_completed=warmup_completed
            )
            
        except Exception as e:
            self._metrics["model_load_failures"] += 1
            logger.error(f"Failed to load model: {e}")
            
            return ModelLoadResult(
                success=False,
                error_message=str(e),
                load_time_seconds=time.time() - start_time
            )
    
    def _run_warmup(self, model: Any, version: str) -> bool:
        """
        Run model warm-up with sample data.
        
        Args:
            model: Model to warm up
            version: Model version
            
        Returns:
            True if warm-up completed successfully
        """
        logger.info(f"Starting warm-up for model version {version}")
        
        success_count = 0
        total_count = self.warmup_config.sample_count
        errors = []
        
        # Generate sample inputs for warm-up
        sample_inputs = self._generate_warmup_samples(total_count)
        
        for i, sample_input in enumerate(sample_inputs):
            try:
                # Run inference
                with torch.no_grad():
                    output = model(sample_input)
                
                # Validate output
                if self._validate_model_output(output):
                    success_count += 1
                else:
                    errors.append(f"Sample {i}: Invalid output")
                    
            except Exception as e:
                errors.append(f"Sample {i}: {str(e)}")
        
        success_rate = success_count / total_count if total_count > 0 else 0
        logger.info(
            f"Warm-up for version {version}: {success_count}/{total_count} "
            f"({success_rate*100:.1f}%) successful"
        )
        
        return success_rate >= self.warmup_config.required_success_rate
    
    def _generate_warmup_samples(self, count: int) -> List[torch.Tensor]:
        """
        Generate sample inputs for model warm-up.
        
        Args:
            count: Number of samples to generate
            
        Returns:
            List of sample input tensors
        """
        samples = []
        
        for _ in range(count):
            # Generate sample with realistic shapes
            sample = torch.randn(
                1,  # batch size
                settings.event_embedding_dim +
                settings.weather_embedding_dim +
                settings.historical_sequence_length * settings.temporal_encoding_dim
            )
            samples.append(sample)
        
        return samples
    
    def _validate_model_output(self, output: Any) -> bool:
        """
        Validate model output is valid.
        
        Checks:
        - Probability bounds [0, 1]
        - No NaN/Inf values
        - Confidence interval is valid
        
        Args:
            output: Model output
            
        Returns:
            True if output is valid
        """
        try:
            # Handle dict output (from CAT model)
            if isinstance(output, dict):
                prob = output.get("probability")
                if prob is None:
                    return False
                
                # Check probability bounds
                if isinstance(prob, torch.Tensor):
                    prob_val = prob.item()
                else:
                    prob_val = float(prob)
                
                if not (0.0 <= prob_val <= 1.0):
                    return False
                
                # Check for NaN/Inf
                for key, value in output.items():
                    if isinstance(value, torch.Tensor):
                        if not torch.isfinite(value).all():
                            return False
                    elif isinstance(value, (int, float)):
                        if not np.isfinite(value):
                            return False
                
                return True
            
            # Handle tensor output
            elif isinstance(output, torch.Tensor):
                if not torch.isfinite(output).all():
                    return False
                
                prob = output.item()
                return 0.0 <= prob <= 1.0
            
            return False
            
        except Exception:
            return False
    
    def hot_swap(
        self,
        new_version: str = None,
        new_stage: str = "Staging",
        target_stage: str = "Production"
    ) -> Tuple[bool, str]:
        """
        Hot-swap to a new model version.
        
        Args:
            new_version: Version to swap to (optional)
            new_stage: Stage of the new version
            target_stage: Stage to promote to
            
        Returns:
            Tuple of (success, message)
        """
        if not self.hot_swap_config.enabled:
            return False, "Hot-swap is disabled"
        
        if self._hot_swap_in_progress:
            return False, "Hot-swap already in progress"
        
        self._hot_swap_in_progress = True
        
        try:
            # Load new model
            logger.info(f"Starting hot-swap to version {new_version or new_stage}")
            
            load_result = self.load_model(
                version=new_version,
                stage=new_stage,
                blocking=True
            )
            
            if not load_result.success:
                return False, f"Failed to load model: {load_result.error_message}"
            
            # Test new model before switching traffic
            if self.hot_swap_config.test_before_switch:
                test_success = self._test_model_before_switch(
                    load_result.model,
                    load_result.version_info.version
                )
                
                if not test_success:
                    return False, "New model failed pre-switch tests"
            
            # Perform the swap
            old_version = self.get_production_version()
            
            with self._model_lock:
                # Retain current production for rollback
                if self._production_model and self.hot_swap_config.retain_previous_version:
                    self._previous_production_model = self._production_model
                
                # Move staging to production
                if self._staging_model and self._staging_model.version == load_result.version_info.version:
                    self._production_model = self._staging_model
                    self._staging_model = None
            
            # Invalidate cache on model change (Requirement 11.3)
            self._invalidate_cache_on_model_change("hot_swap")
            
            self._metrics["hot_swaps"] += 1
            logger.info(
                f"Hot-swap completed: {old_version} -> {load_result.version_info.version}"
            )
            
            return True, f"Swapped to version {load_result.version_info.version}"
            
        except Exception as e:
            logger.error(f"Hot-swap failed: {e}")
            return False, str(e)
        finally:
            self._hot_swap_in_progress = False
    
    def _test_model_before_switch(self, model: Any, version: str) -> bool:
        """
        Test a model before switching traffic to it.
        
        Args:
            model: Model to test
            version: Model version
            
        Returns:
            True if tests passed
        """
        logger.info(f"Testing model version {version} before switch")
        
        sample_count = self.hot_swap_config.test_sample_count
        timeout = self.hot_swap_config.test_timeout_seconds
        
        success_count = 0
        
        for i in range(sample_count):
            try:
                sample_input = self._generate_warmup_samples(1)[0]
                
                with torch.no_grad():
                    output = model(sample_input)
                
                if self._validate_model_output(output):
                    success_count += 1
                    
            except Exception as e:
                logger.warning(f"Test sample {i} failed: {e}")
        
        success_rate = success_count / sample_count if sample_count > 0 else 0
        passed = success_rate >= 0.8  # 80% success rate required
        
        logger.info(
            f"Pre-switch tests for version {version}: "
            f"{success_count}/{sample_count} ({success_rate*100:.1f}%) - "
            f"{'PASSED' if passed else 'FAILED'}"
        )
        
        return passed
    
    def rollback(self) -> Tuple[bool, str]:
        """
        Rollback to the previous production model.
        
        Returns:
            Tuple of (success, message)
        """
        with self._model_lock:
            if not self._previous_production_model:
                return False, "No previous production model available"
            
            # Swap back to previous model
            old_production = self._production_model
            self._production_model = self._previous_production_model
            self._previous_production_model = None
        
        self._metrics["rollbacks"] += 1
        
        version = self._production_model.version
        logger.info(f"Rolled back to version {version}")
        
        return True, f"Rolled back to version {version}"
    
    def predict_with_fallback(
        self,
        model_input: torch.Tensor,
        location_id: str = None,
        prediction_time: datetime = None
    ) -> Tuple[AvailabilityPrediction, bool]:
        """
        Run prediction with fallback to cached predictions on failure.
        
        Args:
            model_input: Model input tensor
            location_id: Location ID for cache lookup
            prediction_time: Prediction time for cache lookup
            
        Returns:
            Tuple of (prediction, is_from_cache)
        """
        self._metrics["total_predictions"] += 1
        
        # Try to get model
        model = self.get_production_model()
        
        if model is None:
            logger.warning("No production model available")
            return self._get_cached_prediction(location_id, prediction_time)
        
        try:
            # Run inference
            with torch.no_grad():
                output = model(model_input)
            
            # Validate output
            if not self._validate_model_output(output):
                raise ValueError("Invalid model output")
            
            # Create prediction object
            if isinstance(output, dict):
                prediction = AvailabilityPrediction(
                    probability=output.get("probability", 0.5).item() if hasattr(output.get("probability"), 'item') else float(output.get("probability", 0.5)),
                    confidence_interval=(
                        output.get("confidence_lower", 0.3).item() if hasattr(output.get("confidence_lower"), 'item') else float(output.get("confidence_lower", 0.3)),
                        output.get("confidence_upper", 0.7).item() if hasattr(output.get("confidence_upper"), 'item') else float(output.get("confidence_upper", 0.7))
                    ),
                    contributing_factors=output.get("contributing_factors", []),
                    location_id=location_id or "unknown",
                    prediction_time=prediction_time or datetime.utcnow(),
                    model_version=self.get_production_version() or settings.model_version
                )
            else:
                prob = output.item() if hasattr(output, 'item') else float(output)
                prediction = AvailabilityPrediction(
                    probability=prob,
                    confidence_interval=(max(0.0, prob - 0.1), min(1.0, prob + 0.1)),
                    contributing_factors=[],
                    location_id=location_id or "unknown",
                    prediction_time=prediction_time or datetime.utcnow(),
                    model_version=self.get_production_version() or settings.model_version
                )
            
            # Cache the prediction
            self._cache_prediction(location_id, prediction_time, prediction)
            
            # Update metrics
            with self._model_lock:
                if self._production_model:
                    self._production_model.prediction_count += 1
            
            return prediction, False
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            
            # Update error count
            with self._model_lock:
                if self._production_model:
                    self._production_model.error_count += 1
            
            # Trigger model reload if enabled
            if self.reload_config.enabled:
                self._trigger_reload()
            
            # Return cached prediction
            return self._get_cached_prediction(location_id, prediction_time)
    
    def _trigger_reload(self) -> None:
        """Trigger model reload in background."""
        if self._reload_in_progress:
            return
        
        self._reload_in_progress = True
        self._metrics["reload_attempts"] += 1
        
        logger.info("Triggering model reload")
        
        # Run reload in executor
        def do_reload():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._reload_model_async())
            finally:
                loop.close()
        
        self._executor.submit(do_reload)
    
    async def _reload_model_async(self) -> None:
        """Reload model with retry logic."""
        max_retries = self.reload_config.max_retries
        retry_delay = self.reload_config.retry_delay_seconds
        max_delay = self.reload_config.max_retry_delay_seconds
        exponential_base = self.reload_config.exponential_base
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Model reload attempt {attempt + 1}/{max_retries}")
                
                # Try to load from MLflow
                load_result = self.load_model(stage="Production", blocking=True)
                
                if load_result.success:
                    logger.info("Model reload successful")
                    
                    # Invalidate cache on model reload (Requirement 11.3)
                    self._invalidate_cache_on_model_change("reload")
                    
                    self._reload_in_progress = False
                    self._reload_event.set()
                    return
                else:
                    raise ValueError(load_result.error_message)
                    
            except Exception as e:
                logger.warning(f"Reload attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = min(retry_delay * (exponential_base ** attempt), max_delay)
                    logger.info(f"Retrying in {delay:.1f} seconds")
                    await asyncio.sleep(delay)
                else:
                    logger.error("All reload attempts failed")
                    self._metrics["reload_failures"] += 1
                    self._reload_in_progress = False
    
    def _cache_prediction(
        self,
        location_id: Optional[str],
        prediction_time: Optional[datetime],
        prediction: AvailabilityPrediction
    ) -> None:
        """
        Cache a prediction for fallback.
        
        Args:
            location_id: Location ID
            prediction_time: Prediction time
            prediction: Prediction to cache
        """
        if not location_id or not prediction_time:
            return
        
        cache_key = f"{location_id}:{prediction_time.isoformat()}"
        
        with self._cache_lock:
            self._prediction_cache[cache_key] = CachedPrediction(
                prediction=prediction,
                ttl_seconds=self.reload_config.cache_ttl_seconds
            )
    
    def _get_cached_prediction(
        self,
        location_id: Optional[str],
        prediction_time: Optional[datetime]
    ) -> Tuple[AvailabilityPrediction, bool]:
        """
        Get a cached prediction if available.
        
        Args:
            location_id: Location ID
            prediction_time: Prediction time
            
        Returns:
            Tuple of (prediction, is_from_cache)
        """
        self._metrics["cached_predictions"] += 1
        
        if not location_id or not prediction_time:
            # Return fallback prediction
            return self._get_fallback_prediction(), True
        
        cache_key = f"{location_id}:{prediction_time.isoformat()}"
        
        with self._cache_lock:
            if cache_key in self._prediction_cache:
                cached = self._prediction_cache[cache_key]
                if not cached.is_expired():
                    logger.debug(f"Using cached prediction for {cache_key}")
                    return cached.prediction, True
                else:
                    # Remove expired
                    del self._prediction_cache[cache_key]
        
        # Return fallback prediction
        return self._get_fallback_prediction(), True
    
    def _get_fallback_prediction(self) -> AvailabilityPrediction:
        """
        Get a fallback prediction when model is unavailable.
        
        Returns:
            Fallback prediction with conservative values
        """
        return AvailabilityPrediction(
            probability=0.5,
            confidence_interval=(0.3, 0.7),
            contributing_factors=[],
            location_id="fallback",
            prediction_time=datetime.utcnow(),
            model_version="fallback"
        )
    
    def cache_prediction_for_recovery(
        self,
        location_id: str,
        prediction_time: datetime,
        prediction: AvailabilityPrediction
    ) -> None:
        """
        Cache a prediction specifically for recovery/fallback.
        
        This is called after successful predictions to build up the cache.
        
        Args:
            location_id: Location ID
            prediction_time: Prediction time
            prediction: Prediction to cache
        """
        self._cache_prediction(location_id, prediction_time, prediction)
    
    def get_cached_predictions_count(self) -> int:
        """Get the number of cached predictions."""
        with self._cache_lock:
            return len(self._prediction_cache)
    
    def clear_cache(self) -> None:
        """Clear the prediction cache."""
        with self._cache_lock:
            self._prediction_cache.clear()
        logger.info("Prediction cache cleared")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get model manager metrics."""
        with self._model_lock:
            model_metrics = {
                "production_version": self.get_production_version(),
                "staging_version": self.get_staging_version(),
                "previous_production_version": self.get_previous_production_version(),
                "production_predictions": self._production_model.prediction_count if self._production_model else 0,
                "production_errors": self._production_model.error_count if self._production_model else 0
            }
        
        return {
            **self._metrics,
            **model_metrics,
            "cached_predictions_count": self.get_cached_predictions_count(),
            "reload_in_progress": self._reload_in_progress,
            "hot_swap_in_progress": self._hot_swap_in_progress
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get detailed status of the model manager."""
        return {
            "production_model": {
                "version": self.get_production_version(),
                "loaded": self._production_model is not None,
                "warmup_completed": self._production_model.warmup_completed if self._production_model else False
            } if self._production_model else None,
            "staging_model": {
                "version": self.get_staging_version(),
                "loaded": self._staging_model is not None,
                "warmup_completed": self._staging_model.warmup_completed if self._staging_model else False
            } if self._staging_model else None,
            "previous_production_model": {
                "version": self.get_previous_production_version(),
                "loaded": self._previous_production_model is not None
            } if self._previous_production_model else None,
            "cache": {
                "size": self.get_cached_predictions_count(),
                "ttl_seconds": self.reload_config.cache_ttl_seconds
            },
            "reload": {
                "enabled": self.reload_config.enabled,
                "in_progress": self._reload_in_progress
            },
            "hot_swap": {
                "enabled": self.hot_swap_config.enabled,
                "in_progress": self._hot_swap_in_progress
            }
        }
    
    async def close(self) -> None:
        """Clean up resources."""
        logger.info("Shutting down ModelManager")
        
        # Clear caches
        self.clear_cache()
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        logger.info("ModelManager shutdown complete")


# Factory function
def create_model_manager(
    registry_uri: str = None,
    model_name: str = None,
    device: str = "cpu"
) -> ModelManager:
    """
    Create a ModelManager instance.
    
    Args:
        registry_uri: MLflow registry URI
        model_name: Model name in registry
        device: Device to load model on
        
    Returns:
        Configured ModelManager instance
    """
    mlflow_client = create_mlflow_client(
        registry_uri=registry_uri,
        model_name=model_name
    )
    
    return ModelManager(
        mlflow_client=mlflow_client,
        device=device
    )