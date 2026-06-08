"""
Unit tests for the ModelManager class.
Tests model loading, versioning, hot-swapping, warm-up, and failure recovery.
"""

import pytest
import time
import torch
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio

from backend.cat.inference.model_manager import (
    ModelManager,
    ModelWarmupConfig,
    ModelReloadConfig,
    HotSwapConfig,
    CachedPrediction,
    ModelLoadResult
)
from backend.cat.inference.mlflow_client import MLflowClient, ModelVersionInfo
from backend.cat.models.schemas import AvailabilityPrediction


class TestCachedPrediction:
    """Tests for CachedPrediction class."""
    
    def test_cache_creation(self):
        """Test creating a cached prediction."""
        prediction = AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime.utcnow(),
            model_version="1.0.0"
        )
        
        cached = CachedPrediction(prediction, ttl_seconds=300)
        
        assert cached.prediction == prediction
        assert cached.ttl_seconds == 300
        assert not cached.is_expired()
    
    def test_cache_expiration(self):
        """Test cache expiration."""
        prediction = AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime.utcnow(),
            model_version="1.0.0"
        )
        
        # Create cache with old timestamp
        old_time = datetime.utcnow() - timedelta(seconds=400)
        cached = CachedPrediction(prediction, cache_time=old_time, ttl_seconds=300)
        
        assert cached.is_expired()
    
    def test_cache_within_ttl(self):
        """Test checking if cache is within specific TTL."""
        prediction = AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime.utcnow(),
            model_version="1.0.0"
        )
        
        # Create cache with recent timestamp
        recent_time = datetime.utcnow() - timedelta(seconds=100)
        cached = CachedPrediction(prediction, cache_time=recent_time, ttl_seconds=300)
        
        assert cached.is_within_ttl(200)  # Within 200 seconds
        assert not cached.is_within_ttl(50)  # Not within 50 seconds


class TestModelWarmupConfig:
    """Tests for ModelWarmupConfig."""
    
    def test_default_config(self):
        """Test default warm-up configuration."""
        config = ModelWarmupConfig()
        
        assert config.enabled is True
        assert config.sample_count == 10
        assert config.timeout_seconds == 60
        assert config.required_success_rate == 0.9
    
    def test_custom_config(self):
        """Test custom warm-up configuration."""
        config = ModelWarmupConfig(
            enabled=False,
            sample_count=5,
            timeout_seconds=30,
            required_success_rate=0.8
        )
        
        assert config.enabled is False
        assert config.sample_count == 5
        assert config.timeout_seconds == 30
        assert config.required_success_rate == 0.8


class TestModelReloadConfig:
    """Tests for ModelReloadConfig."""
    
    def test_default_config(self):
        """Test default reload configuration."""
        config = ModelReloadConfig()
        
        assert config.enabled is True
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 5.0
        assert config.exponential_base == 2.0
        assert config.max_retry_delay_seconds == 60.0
        assert config.fallback_to_cached is True
        assert config.cache_ttl_seconds == 300  # 5 minutes per requirement 11.3


class TestHotSwapConfig:
    """Tests for HotSwapConfig."""
    
    def test_default_config(self):
        """Test default hot-swap configuration."""
        config = HotSwapConfig()
        
        assert config.enabled is True
        assert config.test_before_switch is True
        assert config.test_sample_count == 5
        assert config.retain_previous_version is True  # Requirement 11.7
        assert config.previous_version_retention_hours == 24


class TestModelManager:
    """Tests for ModelManager class."""
    
    @pytest.fixture
    def mock_mlflow_client(self):
        """Create a mock MLflow client."""
        client = Mock(spec=MLflowClient)
        client.config = Mock()
        client.config.model_name = "cat-test"
        
        def create_version_info(version, stage):
            return ModelVersionInfo(
                version=version,
                stage=stage,
                status="READY",
                creation_timestamp=datetime.utcnow(),
                last_updated_timestamp=datetime.utcnow(),
                description=f"Test model {version}",
                run_id=f"test-run-id-{version}",
                source_path=f"s3://bucket/model-{version}",
                tags={}
            )
        
        def load_artifact(version=None, stage=None):
            v = version or "1"
            s = stage or "Production"
            return Mock(), create_version_info(v, s)
        
        client.load_model_artifact = Mock(side_effect=load_artifact)
        
        return client, create_version_info("1", "Production")
    
    @pytest.fixture
    def model_manager(self, mock_mlflow_client):
        """Create a ModelManager with mocked MLflow client."""
        client, _ = mock_mlflow_client
        
        warmup_config = ModelWarmupConfig(
            enabled=False,  # Disable for faster tests
            sample_count=3
        )
        
        return ModelManager(
            mlflow_client=client,
            warmup_config=warmup_config
        )
    
    def test_initial_state(self, model_manager):
        """Test initial state of model manager."""
        assert model_manager.get_production_model() is None
        assert model_manager.get_production_version() is None
        assert model_manager.get_staging_model() is None
        assert model_manager.get_previous_production_model() is None
        assert model_manager.get_cached_predictions_count() == 0
    
    def test_load_model_success(self, model_manager, mock_mlflow_client):
        """Test successful model loading."""
        client, version_info = mock_mlflow_client
        
        result = model_manager.load_model(version="1", stage="Production")
        
        assert result.success is True
        assert result.model is not None
        assert result.version_info.version == "1"
        # When warmup is disabled, warmup_completed is True (no warmup needed)
        assert result.warmup_completed is True
        assert model_manager.get_production_version() == "1"
    
    def test_load_model_failure(self, model_manager):
        """Test model loading failure."""
        model_manager.mlflow_client.load_model_artifact = Mock(
            side_effect=Exception("MLflow connection failed")
        )
        
        result = model_manager.load_model(version="1", stage="Production")
        
        assert result.success is False
        assert "MLflow connection failed" in result.error_message
        assert model_manager.get_production_model() is None
    
    def test_get_all_versions_empty(self, model_manager):
        """Test getting all versions when none loaded."""
        versions = model_manager.get_all_versions()
        
        assert versions == []
    
    def test_get_all_versions_with_models(self, model_manager, mock_mlflow_client):
        """Test getting all versions with models loaded."""
        _, version_info = mock_mlflow_client
        
        # Load production model
        model_manager.load_model(version="1", stage="Production")
        
        versions = model_manager.get_all_versions()
        
        assert len(versions) == 1
        assert versions[0]["version"] == "1"
        assert versions[0]["stage"] == "Production"
    
    def test_cache_prediction(self, model_manager):
        """Test caching predictions."""
        prediction = AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime.utcnow(),
            model_version="1.0.0"
        )
        
        model_manager.cache_prediction_for_recovery(
            location_id="test_loc",
            prediction_time=datetime.utcnow(),
            prediction=prediction
        )
        
        assert model_manager.get_cached_predictions_count() == 1
    
    def test_get_cached_prediction(self, model_manager):
        """Test retrieving cached predictions."""
        prediction = AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime.utcnow(),
            model_version="1.0.0"
        )
        
        prediction_time = datetime.utcnow()
        model_manager.cache_prediction_for_recovery(
            location_id="test_loc",
            prediction_time=prediction_time,
            prediction=prediction
        )
        
        cached_pred, is_cached = model_manager._get_cached_prediction(
            "test_loc", prediction_time
        )
        
        assert is_cached is True
        assert cached_pred.probability == 0.75
    
    def test_get_cached_prediction_expired(self, model_manager):
        """Test that expired cache returns fallback."""
        prediction = AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime.utcnow(),
            model_version="1.0.0"
        )
        
        # Cache with old timestamp
        old_time = datetime.utcnow() - timedelta(seconds=400)
        model_manager._prediction_cache["test_loc"] = CachedPrediction(
            prediction=prediction,
            cache_time=old_time,
            ttl_seconds=300
        )
        
        cached_pred, is_cached = model_manager._get_cached_prediction(
            "test_loc", datetime.utcnow()
        )
        
        # Should return fallback prediction
        assert is_cached is True
        assert cached_pred.location_id == "fallback"
    
    def test_clear_cache(self, model_manager):
        """Test clearing the prediction cache."""
        # Add some cached predictions
        for i in range(5):
            prediction = AvailabilityPrediction(
                probability=0.5 + i * 0.1,
                confidence_interval=(0.3, 0.7),
                contributing_factors=[],
                location_id=f"loc_{i}",
                prediction_time=datetime.utcnow(),
                model_version="1.0.0"
            )
            model_manager.cache_prediction_for_recovery(
                location_id=f"loc_{i}",
                prediction_time=datetime.utcnow(),
                prediction=prediction
            )
        
        assert model_manager.get_cached_predictions_count() == 5
        
        model_manager.clear_cache()
        
        assert model_manager.get_cached_predictions_count() == 0
    
    def test_rollback_no_previous(self, model_manager):
        """Test rollback when no previous model exists."""
        success, message = model_manager.rollback()
        
        assert success is False
        assert "No previous production model" in message
    
    def test_rollback_success(self, model_manager, mock_mlflow_client):
        """Test successful rollback to previous model."""
        _, version_info = mock_mlflow_client
        
        # Load first model
        model_manager.load_model(version="1", stage="Production")
        
        # Simulate having a previous model
        model_manager._previous_production_model = Mock()
        model_manager._previous_production_model.version = "0"
        
        success, message = model_manager.rollback()
        
        assert success is True
        assert "0" in message
        assert model_manager._previous_production_model is None
    
    def test_hot_swap_disabled(self, model_manager):
        """Test hot-swap when disabled."""
        model_manager.hot_swap_config.enabled = False
        
        success, message = model_manager.hot_swap(new_version="2")
        
        assert success is False
        assert "disabled" in message.lower()
    
    def test_hot_swap_already_in_progress(self, model_manager):
        """Test hot-swap when already in progress."""
        model_manager._hot_swap_in_progress = True
        
        success, message = model_manager.hot_swap(new_version="2")
        
        assert success is False
        assert "in progress" in message.lower()
    
    def test_hot_swap_success(self, model_manager, mock_mlflow_client):
        """Test successful hot-swap."""
        client, version_info = mock_mlflow_client
        
        # Create staging version info
        staging_version_info = ModelVersionInfo(
            version="2",
            stage="Staging",
            status="READY",
            creation_timestamp=datetime.utcnow(),
            last_updated_timestamp=datetime.utcnow(),
            description="Staging model",
            run_id="test-run-id-2",
            source_path="s3://bucket/model-2",
            tags={}
        )
        
        # Create a mock model that returns valid output for pre-switch tests
        def load_artifact(version=None, stage=None):
            mock_model = Mock()
            mock_model.return_value = {
                "probability": torch.tensor(0.75),
                "confidence_lower": torch.tensor(0.65),
                "confidence_upper": torch.tensor(0.85)
            }
            if version == "2":
                return mock_model, staging_version_info
            return mock_model, version_info
        
        client.load_model_artifact = Mock(side_effect=load_artifact)
        
        # First load a production model (version 1)
        result = model_manager.load_model(version="1", stage="Production")
        assert result.success is True
        assert model_manager.get_production_version() == "1"
        
        # Load staging model - this should go to staging slot
        result = model_manager.load_model(version="2", stage="Staging")
        assert result.success is True
        assert model_manager.get_staging_version() == "2"
        
        # Hot-swap to staging
        success, message = model_manager.hot_swap(
            new_version="2",
            new_stage="Staging"
        )
        
        assert success is True, f"Hot-swap failed: {message}"
        assert "2" in message
        assert model_manager.get_production_version() == "2"
        assert model_manager._previous_production_model is not None  # Retained previous
    
    def test_predict_with_fallback_no_model(self, model_manager):
        """Test prediction fallback when no model is loaded."""
        model_input = torch.randn(1, 256)
        
        prediction, is_cached = model_manager.predict_with_fallback(
            model_input=model_input,
            location_id="test_loc",
            prediction_time=datetime.utcnow()
        )
        
        assert is_cached is True
        assert prediction.location_id == "fallback"
    
    def test_predict_with_fallback_model_available(self, model_manager, mock_mlflow_client):
        """Test prediction when model is available."""
        _, version_info = mock_mlflow_client
        
        # Load model
        model_manager.load_model(version="1", stage="Production")
        
        # Create mock model that returns valid output
        mock_output = {
            "probability": torch.tensor(0.75),
            "confidence_lower": torch.tensor(0.65),
            "confidence_upper": torch.tensor(0.85),
            "contributing_factors": []
        }
        model_manager._production_model.model = Mock(return_value=mock_output)
        
        model_input = torch.randn(1, 256)
        
        prediction, is_cached = model_manager.predict_with_fallback(
            model_input=model_input,
            location_id="test_loc",
            prediction_time=datetime.utcnow()
        )
        
        assert is_cached is False
        assert prediction.probability == 0.75
        assert model_manager._production_model.prediction_count == 1
    
    def test_predict_with_fallback_model_error(self, model_manager, mock_mlflow_client):
        """Test prediction fallback when model errors."""
        _, version_info = mock_mlflow_client
        
        # Load model
        model_manager.load_model(version="1", stage="Production")
        
        # Create mock model that raises error
        model_manager._production_model.model = Mock(
            side_effect=Exception("Model error")
        )
        
        model_input = torch.randn(1, 256)
        
        prediction, is_cached = model_manager.predict_with_fallback(
            model_input=model_input,
            location_id="test_loc",
            prediction_time=datetime.utcnow()
        )
        
        assert is_cached is True
        assert prediction.location_id == "fallback"
        assert model_manager._production_model.error_count == 1
    
    def test_get_metrics(self, model_manager, mock_mlflow_client):
        """Test getting model manager metrics."""
        _, version_info = mock_mlflow_client
        
        # Load model
        model_manager.load_model(version="1", stage="Production")
        
        metrics = model_manager.get_metrics()
        
        assert "total_predictions" in metrics
        assert "cached_predictions" in metrics
        assert "model_loads" in metrics
        assert "model_load_failures" in metrics
        assert "production_version" in metrics
        assert metrics["production_version"] == "1"
    
    def test_get_status(self, model_manager, mock_mlflow_client):
        """Test getting model manager status."""
        _, version_info = mock_mlflow_client
        
        # Load model
        model_manager.load_model(version="1", stage="Production")
        
        status = model_manager.get_status()
        
        assert "production_model" in status
        assert status["production_model"]["version"] == "1"
        assert status["production_model"]["loaded"] is True
        assert "cache" in status
        assert "reload" in status
        assert "hot_swap" in status
    
    def test_validate_model_output_valid(self, model_manager):
        """Test validating valid model output."""
        output = {
            "probability": torch.tensor(0.75),
            "confidence_lower": torch.tensor(0.65),
            "confidence_upper": torch.tensor(0.85)
        }
        
        assert model_manager._validate_model_output(output) is True
    
    def test_validate_model_output_invalid_probability(self, model_manager):
        """Test validating output with invalid probability."""
        output = {
            "probability": torch.tensor(1.5),  # > 1.0
            "confidence_lower": torch.tensor(0.65),
            "confidence_upper": torch.tensor(0.85)
        }
        
        assert model_manager._validate_model_output(output) is False
    
    def test_validate_model_output_nan(self, model_manager):
        """Test validating output with NaN values."""
        output = {
            "probability": torch.tensor(float('nan')),
            "confidence_lower": torch.tensor(0.65),
            "confidence_upper": torch.tensor(0.85)
        }
        
        assert model_manager._validate_model_output(output) is False
    
    def test_validate_model_output_inf(self, model_manager):
        """Test validating output with Inf values."""
        output = {
            "probability": torch.tensor(float('inf')),
            "confidence_lower": torch.tensor(0.65),
            "confidence_upper": torch.tensor(0.85)
        }
        
        assert model_manager._validate_model_output(output) is False
    
    def test_generate_warmup_samples(self, model_manager):
        """Test generating warm-up samples."""
        samples = model_manager._generate_warmup_samples(5)
        
        assert len(samples) == 5
        for sample in samples:
            assert isinstance(sample, torch.Tensor)
            assert sample.shape[0] == 1  # batch size
    
    def test_retain_previous_version_on_load(self, model_manager, mock_mlflow_client):
        """Test that previous version is retained when loading new model."""
        _, version_info = mock_mlflow_client
        
        # Load first model
        model_manager.load_model(version="1", stage="Production")
        assert model_manager._previous_production_model is None
        
        # Load second model (should retain first)
        model_manager.load_model(version="2", stage="Production")
        
        assert model_manager._previous_production_model is not None
        assert model_manager._previous_production_model.version == "1"
    
    def test_cache_ttl_five_minutes(self, model_manager):
        """Test that cache TTL is 5 minutes as per requirement 11.3."""
        assert model_manager.reload_config.cache_ttl_seconds == 300  # 5 minutes


class TestModelManagerWithWarmup:
    """Tests for ModelManager with warm-up enabled."""
    
    @pytest.fixture
    def mock_mlflow_client(self):
        """Create a mock MLflow client."""
        client = Mock(spec=MLflowClient)
        client.config = Mock()
        client.config.model_name = "cat-test"
        
        version_info = ModelVersionInfo(
            version="1",
            stage="Production",
            status="READY",
            creation_timestamp=datetime.utcnow(),
            last_updated_timestamp=datetime.utcnow(),
            description="Test model",
            run_id="test-run-id",
            source_path="s3://bucket/model",
            tags={}
        )
        client.load_model_artifact = Mock(return_value=(Mock(), version_info))
        
        return client, version_info
    
    def test_warmup_success(self, mock_mlflow_client):
        """Test successful model warm-up."""
        client, version_info = mock_mlflow_client
        
        # Create model that returns valid outputs
        mock_model = Mock()
        mock_model.return_value = {
            "probability": torch.tensor(0.75),
            "confidence_lower": torch.tensor(0.65),
            "confidence_upper": torch.tensor(0.85)
        }
        
        client.load_model_artifact = Mock(return_value=(mock_model, version_info))
        
        warmup_config = ModelWarmupConfig(
            enabled=True,
            sample_count=5,
            required_success_rate=0.8
        )
        
        manager = ModelManager(
            mlflow_client=client,
            warmup_config=warmup_config
        )
        
        result = manager.load_model(version="1", stage="Production")
        
        assert result.success is True
        assert result.warmup_completed is True
    
    def test_warmup_failure(self, mock_mlflow_client):
        """Test model warm-up failure."""
        client, version_info = mock_mlflow_client
        
        # Create model that returns invalid outputs
        mock_model = Mock()
        mock_model.return_value = {
            "probability": torch.tensor(1.5),  # Invalid probability
            "confidence_lower": torch.tensor(0.65),
            "confidence_upper": torch.tensor(0.85)
        }
        
        client.load_model_artifact = Mock(return_value=(mock_model, version_info))
        
        warmup_config = ModelWarmupConfig(
            enabled=True,
            sample_count=5,
            required_success_rate=0.8
        )
        
        manager = ModelManager(
            mlflow_client=client,
            warmup_config=warmup_config
        )
        
        result = manager.load_model(version="1", stage="Production")
        
        assert result.success is True
        assert result.warmup_completed is False


class TestModelManagerIntegration:
    """Integration tests for ModelManager."""
    
    @pytest.fixture
    def mock_mlflow_client(self):
        """Create a mock MLflow client for integration tests."""
        client = Mock(spec=MLflowClient)
        client.config = Mock()
        client.config.model_name = "cat-integration-test"
        
        def create_version_info(version, stage):
            return ModelVersionInfo(
                version=version,
                stage=stage,
                status="READY",
                creation_timestamp=datetime.utcnow(),
                last_updated_timestamp=datetime.utcnow(),
                description=f"Model version {version}",
                run_id=f"run-{version}",
                source_path=f"s3://bucket/model-{version}",
                tags={}
            )
        
        client.load_model_artifact = Mock(
            side_effect=lambda version=None, stage=None: (
                Mock(),
                create_version_info(version or "1", stage or "Production")
            )
        )
        
        return client
    
    def test_full_hot_swap_flow(self, mock_mlflow_client):
        """Test complete hot-swap flow."""
        warmup_config = ModelWarmupConfig(enabled=False)
        hot_swap_config = HotSwapConfig(
            enabled=True,
            test_before_switch=True,
            retain_previous_version=True
        )
        
        manager = ModelManager(
            mlflow_client=mock_mlflow_client,
            warmup_config=warmup_config,
            hot_swap_config=hot_swap_config
        )
        
        # Create version infos
        production_version_info = ModelVersionInfo(
            version="1",
            stage="Production",
            status="READY",
            creation_timestamp=datetime.utcnow(),
            last_updated_timestamp=datetime.utcnow(),
            description="Production model",
            run_id="run-1",
            source_path="s3://bucket/model-1",
            tags={}
        )
        
        staging_version_info = ModelVersionInfo(
            version="2",
            stage="Staging",
            status="READY",
            creation_timestamp=datetime.utcnow(),
            last_updated_timestamp=datetime.utcnow(),
            description="Staging model",
            run_id="run-2",
            source_path="s3://bucket/model-2",
            tags={}
        )
        
        # Create a mock model that returns valid output for pre-switch tests
        def create_mock_model():
            mock_model = Mock()
            mock_model.return_value = {
                "probability": torch.tensor(0.75),
                "confidence_lower": torch.tensor(0.65),
                "confidence_upper": torch.tensor(0.85)
            }
            return mock_model
        
        def load_artifact(version=None, stage=None):
            if version == "2":
                return create_mock_model(), staging_version_info
            return create_mock_model(), production_version_info
        
        mock_mlflow_client.load_model_artifact = Mock(side_effect=load_artifact)
        
        # Load initial production model
        manager.load_model(version="1", stage="Production")
        assert manager.get_production_version() == "1"
        
        # Load staging model
        manager.load_model(version="2", stage="Staging")
        assert manager.get_staging_version() == "2"
        
        # Hot-swap to staging
        success, message = manager.hot_swap(new_version="2", new_stage="Staging")
        assert success is True, f"Hot-swap failed: {message}"
        assert manager.get_production_version() == "2"
        
        # Previous model should be retained
        assert manager.get_previous_production_version() == "1"
    
    def test_rollback_after_hot_swap(self, mock_mlflow_client):
        """Test rollback after hot-swap."""
        manager = ModelManager(
            mlflow_client=mock_mlflow_client,
            warmup_config=ModelWarmupConfig(enabled=False)
        )
        
        # Load initial model
        manager.load_model(version="1", stage="Production")
        
        # Simulate having a previous model
        manager._previous_production_model = Mock()
        manager._previous_production_model.version = "0"
        
        # Rollback
        success, message = manager.rollback()
        assert success is True
        assert manager.get_production_version() == "0"
    
    def test_failure_recovery_with_cache(self, mock_mlflow_client):
        """Test failure recovery using cached predictions."""
        manager = ModelManager(
            mlflow_client=mock_mlflow_client,
            warmup_config=ModelWarmupConfig(enabled=False)
        )
        
        # Load model
        manager.load_model(version="1", stage="Production")
        
        # Cache a prediction
        cached_pred = AvailabilityPrediction(
            probability=0.8,
            confidence_interval=(0.7, 0.9),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime.utcnow(),
            model_version="1.0.0"
        )
        manager.cache_prediction_for_recovery(
            location_id="test_loc",
            prediction_time=datetime.utcnow(),
            prediction=cached_pred
        )
        
        # Make model error
        manager._production_model.model = Mock(side_effect=Exception("Error"))
        
        # Request prediction
        model_input = torch.randn(1, 256)
        prediction, is_cached = manager.predict_with_fallback(
            model_input=model_input,
            location_id="test_loc",
            prediction_time=datetime.utcnow()
        )
        
        # Should return cached prediction
        assert is_cached is True
        assert prediction.probability == 0.8


class TestModelLoadResult:
    """Tests for ModelLoadResult dataclass."""
    
    def test_successful_result(self):
        """Test creating a successful load result."""
        version_info = ModelVersionInfo(
            version="1",
            stage="Production",
            status="READY",
            creation_timestamp=datetime.utcnow(),
            last_updated_timestamp=datetime.utcnow(),
            description="Test",
            run_id="run-1",
            source_path="s3://bucket/model",
            tags={}
        )
        
        result = ModelLoadResult(
            success=True,
            model=Mock(),
            version_info=version_info,
            load_time_seconds=1.5,
            warmup_completed=True
        )
        
        assert result.success is True
        assert result.model is not None
        assert result.version_info.version == "1"
        assert result.load_time_seconds == 1.5
        assert result.warmup_completed is True
    
    def test_failed_result(self):
        """Test creating a failed load result."""
        result = ModelLoadResult(
            success=False,
            error_message="Connection failed",
            load_time_seconds=0.5
        )
        
        assert result.success is False
        assert result.model is None
        assert result.error_message == "Connection failed"
        assert result.warmup_completed is False