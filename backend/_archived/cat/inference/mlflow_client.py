"""
MLflow client integration for the Contextual Availability Transformer (CAT) system.
Handles model registry operations, version tracking, and artifact loading.
"""

import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse

import mlflow
import mlflow.pytorch
import mlflow.sklearn
from mlflow.exceptions import MlflowException

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelVersionInfo:
    """Information about a model version from MLflow registry."""
    version: str
    stage: str
    status: str
    creation_timestamp: datetime
    last_updated_timestamp: datetime
    description: str
    run_id: str
    source_path: str
    tags: Dict[str, str]


@dataclass
class ModelRegistryConfig:
    """Configuration for MLflow model registry."""
    registry_uri: str = "http://localhost:5000"
    registry_tracking_uri: str = "http://localhost:5000"
    model_name: str = "cat-availability-transformer"
    model_stage: str = "Production"
    cache_dir: str = "/tmp/mlflow_cache"
    cache_max_size_mb: int = 1024
    artifact_retention_days: int = 30


class MLflowClient:
    """
    Client for interacting with MLflow model registry.
    
    Provides methods for:
    - Loading models from registry
    - Tracking model versions and stages
    - Managing model stage transitions
    - Caching model artifacts locally
    """
    
    def __init__(
        self,
        config: ModelRegistryConfig = None,
        mlflow_client: mlflow.MlflowClient = None
    ):
        """
        Initialize the MLflow client.
        
        Args:
            config: Registry configuration
            mlflow_client: Optional MLflow client instance for testing
        """
        self.config = config or ModelRegistryConfig(
            model_name=settings.model_name
        )
        
        # Initialize MLflow client
        if mlflow_client is not None:
            self._client = mlflow_client
        else:
            # Set up MLflow tracking and registry URIs
            mlflow.set_tracking_uri(self.config.registry_uri)
            mlflow.set_registry_uri(self.config.registry_uri)
            self._client = mlflow.MlflowClient()
        
        # Local cache for model artifacts
        self._cache_dir = Path(self.config.cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Track loaded models
        self._loaded_models: Dict[str, Tuple[Any, datetime]] = {}
        self._model_locks: Dict[str, bool] = {}
        
        logger.info(f"MLflow client initialized with registry: {self.config.registry_uri}")
    
    def get_registered_model_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the registered model.
        
        Returns:
            Model information dict or None if not found
        """
        try:
            model = self._client.get_registered_model(self.config.model_name)
            return {
                "name": model.name,
                "creation_timestamp": model.creation_timestamp,
                "last_updated_timestamp": model.last_updated_timestamp,
                "description": model.description,
                "latest_versions": [
                    {
                        "version": v.version,
                        "stage": v.current_stage,
                        "status": v.status
                    }
                    for v in model.latest_versions
                ]
            }
        except MlflowException as e:
            logger.warning(f"Model not found in registry: {e}")
            return None
    
    def get_model_versions(self) -> List[ModelVersionInfo]:
        """
        Get all versions of the registered model.
        
        Returns:
            List of ModelVersionInfo objects
        """
        try:
            versions = self._client.get_latest_versions(
                self.config.model_name,
                stages=["None", "Staging", "Production", "Archived"]
            )
            
            return [
                ModelVersionInfo(
                    version=v.version,
                    stage=v.current_stage,
                    status=v.status,
                    creation_timestamp=datetime.fromtimestamp(v.creation_timestamp / 1000),
                    last_updated_timestamp=datetime.fromtimestamp(v.last_updated_timestamp / 1000),
                    description=v.description or "",
                    run_id=v.run_id,
                    source_path=v.source,
                    tags=v.tags or {}
                )
                for v in versions
            ]
        except MlflowException as e:
            logger.error(f"Failed to get model versions: {e}")
            return []
    
    def get_production_version(self) -> Optional[ModelVersionInfo]:
        """
        Get the current production version of the model.
        
        Returns:
            Production ModelVersionInfo or None
        """
        try:
            versions = self._client.get_latest_versions(
                self.config.model_name,
                stages=["Production"]
            )
            
            if versions:
                v = versions[0]
                return ModelVersionInfo(
                    version=v.version,
                    stage=v.current_stage,
                    status=v.status,
                    creation_timestamp=datetime.fromtimestamp(v.creation_timestamp / 1000),
                    last_updated_timestamp=datetime.fromtimestamp(v.last_updated_timestamp / 1000),
                    description=v.description or "",
                    run_id=v.run_id,
                    source_path=v.source,
                    tags=v.tags or {}
                )
        except MlflowException as e:
            logger.error(f"Failed to get production version: {e}")
        
        return None
    
    def get_staging_versions(self) -> List[ModelVersionInfo]:
        """
        Get all staging versions of the model.
        
        Returns:
            List of staging ModelVersionInfo objects
        """
        try:
            versions = self._client.get_latest_versions(
                self.config.model_name,
                stages=["Staging"]
            )
            
            return [
                ModelVersionInfo(
                    version=v.version,
                    stage=v.current_stage,
                    status=v.status,
                    creation_timestamp=datetime.fromtimestamp(v.creation_timestamp / 1000),
                    last_updated_timestamp=datetime.fromtimestamp(v.last_updated_timestamp / 1000),
                    description=v.description or "",
                    run_id=v.run_id,
                    source_path=v.source,
                    tags=v.tags or {}
                )
                for v in versions
            ]
        except MlflowException as e:
            logger.error(f"Failed to get staging versions: {e}")
            return []
    
    def transition_model_stage(
        self,
        version: str,
        target_stage: str,
        archive_existing: bool = False
    ) -> bool:
        """
        Transition a model version to a new stage.
        
        Args:
            version: Model version number
            target_stage: Target stage (Staging, Production, Archived)
            archive_existing: Whether to archive existing models in target stage
            
        Returns:
            True if successful
        """
        try:
            # Archive existing production model if requested
            if target_stage == "Production" and archive_existing:
                existing = self.get_production_version()
                if existing:
                    self._client.transition_model_version_stage(
                        name=self.config.model_name,
                        version=existing.version,
                        stage="Archived"
                    )
            
            # Transition the model
            self._client.transition_model_version_stage(
                name=self.config.model_name,
                version=version,
                stage=target_stage
            )
            
            logger.info(f"Model {self.config.model_name}:{version} transitioned to {target_stage}")
            return True
            
        except MlflowException as e:
            logger.error(f"Failed to transition model stage: {e}")
            return False
    
    def _get_cached_model_path(self, version: str) -> Optional[Path]:
        """
        Get path to cached model for a version.
        
        Args:
            version: Model version
            
        Returns:
            Path to cached model or None
        """
        cache_path = self._cache_dir / f"model_{version}"
        if cache_path.exists():
            return cache_path
        return None
    
    def _cache_model_artifact(self, version: str, source_path: str) -> Path:
        """
        Download and cache model artifact.
        
        Args:
            version: Model version
            source_path: MLflow source path
            
        Returns:
            Path to cached model
        """
        cache_path = self._cache_dir / f"model_{version}"
        
        if cache_path.exists():
            logger.debug(f"Using cached model for version {version}")
            return cache_path
        
        # Create cache directory
        cache_path.mkdir(parents=True, exist_ok=True)
        
        # Download artifact
        try:
            local_path = mlflow.artifacts.download_artifacts(
                artifact_uri=source_path,
                dst_path=str(cache_path)
            )
            
            # If it's a directory, move contents to cache_path
            local_path = Path(local_path)
            if local_path.is_file():
                # Single file artifact
                shutil.move(str(local_path), str(cache_path / "model.pt"))
            elif local_path.is_dir():
                # Directory artifact - move contents
                for item in local_path.iterdir():
                    shutil.move(str(item), str(cache_path / item.name))
                local_path.rmdir()
            
            logger.info(f"Cached model version {version} at {cache_path}")
            return cache_path
            
        except Exception as e:
            logger.error(f"Failed to cache model artifact: {e}")
            if cache_path.exists():
                shutil.rmtree(cache_path)
            raise
    
    def load_model_artifact(
        self,
        version: str = None,
        stage: str = "Production"
    ) -> Tuple[Any, ModelVersionInfo]:
        """
        Load model artifact from MLflow registry.
        
        Args:
            version: Specific version to load (optional)
            stage: Stage to load from if version not specified
            
        Returns:
            Tuple of (loaded model, model version info)
        """
        # Get model version info
        if version:
            versions = self._client.get_latest_versions(
                self.config.model_name,
                stages=["None"]
            )
            version_info = None
            for v in versions:
                if v.version == version:
                    version_info = ModelVersionInfo(
                        version=v.version,
                        stage=v.current_stage,
                        status=v.status,
                        creation_timestamp=datetime.fromtimestamp(v.creation_timestamp / 1000),
                        last_updated_timestamp=datetime.fromtimestamp(v.last_updated_timestamp / 1000),
                        description=v.description or "",
                        run_id=v.run_id,
                        source_path=v.source,
                        tags=v.tags or {}
                    )
                    break
            
            if not version_info:
                raise ValueError(f"Model version {version} not found")
        else:
            versions = self._client.get_latest_versions(
                self.config.model_name,
                stages=[stage]
            )
            if not versions:
                raise ValueError(f"No model found in stage {stage}")
            
            v = versions[0]
            version_info = ModelVersionInfo(
                version=v.version,
                stage=v.current_stage,
                status=v.status,
                creation_timestamp=datetime.fromtimestamp(v.creation_timestamp / 1000),
                last_updated_timestamp=datetime.fromtimestamp(v.last_updated_timestamp / 1000),
                description=v.description or "",
                run_id=v.run_id,
                source_path=v.source,
                tags=v.tags or {}
            )
        
        # Check cache
        cache_key = f"{self.config.model_name}:{version_info.version}"
        if cache_key in self._loaded_models:
            model, timestamp = self._loaded_models[cache_key]
            # Check if cache is still valid (1 hour)
            if (datetime.utcnow() - timestamp).total_seconds() < 3600:
                logger.debug(f"Using in-memory cached model {cache_key}")
                return model, version_info
        
        # Download and cache artifact
        model_path = self._cache_model_artifact(version_info.version, version_info.source_path)
        
        # Load model based on type
        try:
            # Try loading as PyTorch model
            model = mlflow.pytorch.load_model(str(model_path))
        except Exception as e:
            logger.debug(f"Failed to load as PyTorch: {e}")
            try:
                # Try loading as sklearn model
                model = mlflow.sklearn.load_model(str(model_path))
            except Exception as e2:
                logger.error(f"Failed to load model: {e2}")
                raise ValueError(f"Cannot load model from {model_path}")
        
        # Cache in memory
        self._loaded_models[cache_key] = (model, datetime.utcnow())
        
        return model, version_info
    
    def log_model(
        self,
        model: Any,
        artifact_path: str = "model",
        metrics: Dict[str, float] = None,
        params: Dict[str, str] = None,
        tags: Dict[str, str] = None
    ) -> str:
        """
        Log a model to MLflow.
        
        Args:
            model: Model to log
            artifact_path: Path for the artifact
            metrics: Metrics to log
            params: Parameters to log
            tags: Tags to add
            
        Returns:
            Run ID of the logged model
        """
        with mlflow.start_run() as run:
            # Log parameters
            if params:
                for key, value in params.items():
                    mlflow.log_param(key, value)
            
            # Log metrics
            if metrics:
                for key, value in metrics.items():
                    mlflow.log_metric(key, value)
            
            # Log tags
            if tags:
                for key, value in tags.items():
                    mlflow.set_tag(key, value)
            
            # Log model based on type
            if hasattr(model, 'state_dict'):
                # PyTorch model
                mlflow.pytorch.log_model(model, artifact_path)
            elif hasattr(model, 'predict'):
                # Sklearn model
                mlflow.sklearn.log_model(model, artifact_path)
            else:
                # Generic model
                mlflow.pyfunc.log_model(
                    artifact_path=artifact_path,
                    python_model=model,
                    conda_env={"python": ">=3.8.0"}
                )
            
            run_id = run.info.run_id
            logger.info(f"Model logged to MLflow with run_id: {run_id}")
            
            return run_id
    
    def register_model(
        self,
        run_id: str,
        name: str = None,
        description: str = ""
    ) -> Any:
        """
        Register a model from a run.
        
        Args:
            run_id: Run ID containing the model
            name: Model name (uses config if not provided)
            description: Model description
            
        Returns:
            Registered model version info
        """
        model_name = name or self.config.model_name
        
        try:
            # Create model if it doesn't exist
            try:
                self._client.create_registered_model(model_name)
            except MlflowException:
                pass  # Model already exists
            
            # Create version
            version = self._client.create_model_version(
                name=model_name,
                source=f"runs:/{run_id}/model",
                run_id=run_id,
                description=description
            )
            
            logger.info(f"Model {model_name} version {version.version} registered")
            return version
            
        except MlflowException as e:
            logger.error(f"Failed to register model: {e}")
            raise
    
    def delete_model_version(self, version: str) -> bool:
        """
        Delete a model version.
        
        Args:
            version: Model version to delete
            
        Returns:
            True if successful
        """
        try:
            self._client.delete_model_version(
                name=self.config.model_name,
                version=version
            )
            logger.info(f"Model version {version} deleted")
            return True
        except MlflowException as e:
            logger.error(f"Failed to delete model version: {e}")
            return False
    
    def get_model_download_uri(self, version: str) -> Optional[str]:
        """
        Get download URI for a model version.
        
        Args:
            version: Model version
            
        Returns:
            Download URI or None
        """
        try:
            mv = self._client.get_model_version(
                name=self.config.model_name,
                version=version
            )
            return mv.source
        except MlflowException as e:
            logger.error(f"Failed to get download URI: {e}")
            return None
    
    def search_models(
        self,
        filter_string: str = None,
        max_results: int = 10
    ) -> List[Any]:
        """
        Search for model versions.
        
        Args:
            filter_string: MLflow filter string
            max_results: Maximum results to return
            
        Returns:
            List of matching model version objects
        """
        try:
            return self._client.search_model_versions(
                filter_string=filter_string or f"name='{self.config.model_name}'",
                max_results=max_results
            )
        except MlflowException as e:
            logger.error(f"Failed to search models: {e}")
            return []
    
    def cleanup_cache(self, max_age_days: int = 7) -> int:
        """
        Clean up old cached model artifacts.
        
        Args:
            max_age_days: Maximum age in days
            
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        max_age_seconds = max_age_days * 86400
        now = datetime.utcnow().timestamp()
        
        for cache_dir in self._cache_dir.iterdir():
            if cache_dir.is_dir():
                age = now - cache_dir.stat().st_mtime
                if age > max_age_seconds:
                    shutil.rmtree(cache_dir)
                    deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} cached model directories")
        return deleted_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Cache statistics dict
        """
        total_size = 0
        file_count = 0
        
        for cache_dir in self._cache_dir.iterdir():
            if cache_dir.is_dir():
                for file in cache_dir.rglob("*"):
                    if file.is_file():
                        total_size += file.stat().st_size
                        file_count += 1
        
        return {
            "cache_dir": str(self._cache_dir),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "file_count": file_count,
            "loaded_models_count": len(self._loaded_models)
        }


# Factory function
def create_mlflow_client(
    registry_uri: str = None,
    model_name: str = None
) -> MLflowClient:
    """
    Create an MLflow client instance.
    
    Args:
        registry_uri: MLflow registry URI
        model_name: Model name in registry
        
    Returns:
        Configured MLflowClient instance
    """
    config = ModelRegistryConfig(
        registry_uri=registry_uri or settings.mlflow_registry_uri or "http://localhost:5000",
        model_name=model_name or settings.model_name
    )
    
    return MLflowClient(config=config)