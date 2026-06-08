"""
Security tests for the Contextual Availability Transformer (CAT) system.
Tests TLS configuration, secrets management, input validation, and audit logging.
"""

import pytest
import ssl
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from cat.security.tls_config import TLSConfig, create_tls_context
from cat.security.secrets_manager import SecretsManager, create_secrets_manager
from cat.security.input_validator import InputValidator, validate_request
from cat.security.audit_logger import AuditLogger, create_audit_logger
from cat.models.schemas import PredictionRequest, BatchPredictionRequest
from cat.config import settings


class TestTLSConfig:
    """Tests for TLS configuration."""
    
    def test_tls_config_creation(self):
        """Test TLS configuration creation."""
        config = TLSConfig()
        
        assert config is not None
        assert config.min_tls_version == "TLSv1_2"
        assert config.verify_client is False
    
    def test_tls_config_with_paths(self):
        """Test TLS configuration with certificate paths."""
        config = TLSConfig(
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
            min_tls_version="TLSv1_2"
        )
        
        assert config.cert_path is not None
        assert config.key_path is not None
        assert config.min_tls_version == "TLSv1_2"
    
    def test_tls_config_invalid_version(self):
        """Test TLS configuration with invalid version."""
        config = TLSConfig(min_tls_version="TLSv1_0")
        
        # Should default to TLSv1_2
        assert config.min_tls_version == "TLSv1_2"
    
    def test_create_tls_context(self):
        """Test TLS context creation."""
        config = TLSConfig()
        context = config.create_context()
        
        assert context is not None
        assert isinstance(context, ssl.SSLContext)
        assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
    
    def test_is_enabled_without_certs(self):
        """Test is_enabled returns False without certificates."""
        config = TLSConfig()
        
        assert config.is_enabled() is False
    
    def test_is_enabled_with_certs(self):
        """Test is_enabled returns True with certificates."""
        # Create mock certificate files
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = True
            config = TLSConfig(
                cert_path="/path/to/cert.pem",
                key_path="/path/to/key.pem"
            )
            
            assert config.is_enabled() is True
    
    def test_get_config_dict(self):
        """Test configuration dictionary."""
        config = TLSConfig(
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem"
        )
        
        config_dict = config.get_config_dict()
        
        assert "enabled" in config_dict
        assert "min_tls_version" in config_dict
        assert "cert_path" in config_dict


class TestSecretsManager:
    """Tests for secrets management."""
    
    def test_secrets_manager_creation(self):
        """Test secrets manager creation."""
        manager = SecretsManager()
        
        assert manager is not None
        assert manager.rotation_interval_days == 90
    
    def test_get_secret_from_environment(self):
        """Test getting secret from environment."""
        # Set environment variable
        os.environ["CAT_EVENT_API_KEY"] = "test_api_key_123"
        
        try:
            manager = SecretsManager()
            secret = manager.get_secret("event_api_key")
            
            assert secret == "test_api_key_123"
        finally:
            # Clean up
            if "CAT_EVENT_API_KEY" in os.environ:
                del os.environ["CAT_EVENT_API_KEY"]
    
    def test_set_and_get_secret(self):
        """Test setting and getting a secret."""
        manager = SecretsManager()
        
        manager.set_secret("test_secret", "test_value")
        secret = manager.get_secret("test_secret")
        
        assert secret == "test_value"
    
    def test_rotate_secret(self):
        """Test secret rotation."""
        manager = SecretsManager()
        
        # Set initial secret
        manager.set_secret("rotatable_secret", "initial_value")
        initial_value = manager.get_secret("rotatable_secret")
        
        # Rotate
        new_value = manager.rotate_secret("rotatable_secret")
        
        assert new_value != initial_value
        assert manager.get_secret("rotatable_secret") == new_value
    
    def test_check_rotation_needed(self):
        """Test rotation check."""
        manager = SecretsManager(rotation_interval_days=90)
        
        # Set secret and rotation timestamp
        manager.set_secret("test_secret", "value")
        manager._rotation_timestamps["test_secret"] = (
            datetime.utcnow().timestamp() - (91 * 24 * 3600)
        )
        
        # Should need rotation
        assert manager.check_rotation_needed("test_secret") is True
    
    def test_validate_secret(self):
        """Test secret validation."""
        manager = SecretsManager()
        
        manager.set_secret("test_secret", "secret_value")
        
        # Valid secret
        assert manager.validate_secret("test_secret", "secret_value") is True
        
        # Invalid secret
        assert manager.validate_secret("test_secret", "wrong_value") is False
    
    def test_get_all_secrets_masked(self):
        """Test getting all secrets with masking."""
        manager = SecretsManager()
        
        manager.set_secret("secret1", "value1")
        manager.set_secret("secret2", "value2")
        
        secrets = manager.get_all_secrets()
        
        # Values should be masked (either "***" or None)
        for value in secrets.values():
            assert value in ["***", None]
    
    def test_clear_cache(self):
        """Test clearing secrets cache."""
        manager = SecretsManager()
        
        manager.set_secret("test_secret", "value")
        manager._cache["test_secret"] = "value"
        
        manager.clear_cache()
        
        assert "test_secret" not in manager._cache


class TestInputValidator:
    """Tests for input validation."""
    
    def test_validator_creation(self):
        """Test validator creation."""
        validator = InputValidator()
        
        assert validator is not None
        assert validator.max_request_size == 10 * 1024 * 1024
    
    def test_validate_location_id_valid(self):
        """Test valid location ID."""
        validator = InputValidator()
        
        valid, error = validator.validate_location_id("downtown_parking_0001")
        
        assert valid is True
        assert error is None
    
    def test_validate_location_id_empty(self):
        """Test empty location ID."""
        validator = InputValidator()
        
        valid, error = validator.validate_location_id("")
        
        assert valid is False
        assert error is not None
    
    def test_validate_location_id_with_injection(self):
        """Test location ID with injection attempt."""
        validator = InputValidator()
        
        malicious_id = "test'; DROP TABLE users;--"
        valid, error = validator.validate_location_id(malicious_id)
        
        assert valid is False
        assert error is not None
    
    def test_validate_location_id_invalid_chars(self):
        """Test location ID with invalid characters."""
        validator = InputValidator()
        
        invalid_id = "test location with spaces!"
        valid, error = validator.validate_location_id(invalid_id)
        
        assert valid is False
        assert error is not None
    
    def test_validate_prediction_time_valid(self):
        """Test valid prediction time."""
        validator = InputValidator()
        
        future_time = datetime.utcnow() + timedelta(hours=2)
        valid, error = validator.validate_prediction_time(future_time)
        
        assert valid is True
        assert error is None
    
    def test_validate_prediction_time_past(self):
        """Test past prediction time."""
        validator = InputValidator()
        
        past_time = datetime.utcnow() - timedelta(hours=2)
        valid, error = validator.validate_prediction_time(past_time)
        
        assert valid is False
        assert error is not None
    
    def test_validate_prediction_time_exceeds_horizon(self):
        """Test prediction time exceeds horizon."""
        validator = InputValidator()
        
        future_time = datetime.utcnow() + timedelta(hours=200)
        valid, error = validator.validate_prediction_time(future_time)
        
        assert valid is False
        assert error is not None
    
    def test_validate_context_hours_valid(self):
        """Test valid context hours."""
        validator = InputValidator()
        
        valid, error = validator.validate_context_hours(24)
        
        assert valid is True
        assert error is None
    
    def test_validate_context_hours_invalid(self):
        """Test invalid context hours."""
        validator = InputValidator()
        
        valid, error = validator.validate_context_hours(0)
        
        assert valid is False
        assert error is not None
    
    def test_validate_batch_size_valid(self):
        """Test valid batch size."""
        validator = InputValidator()
        
        predictions = [Mock() for _ in range(10)]
        valid, error = validator.validate_batch_size(predictions)
        
        assert valid is True
        assert error is None
    
    def test_validate_batch_size_too_large(self):
        """Test batch size exceeds limit."""
        validator = InputValidator()
        
        predictions = [Mock() for _ in range(150)]
        valid, error = validator.validate_batch_size(predictions)
        
        assert valid is False
        assert error is not None
    
    def test_validate_prediction_request(self):
        """Test full prediction request validation."""
        validator = InputValidator()
        
        request = PredictionRequest(
            location_id="test_location",
            prediction_time=datetime.utcnow() + timedelta(hours=2),
            context_hours=24
        )
        
        valid, error = validator.validate_prediction_request(request)
        
        assert valid is True
        assert error is None
    
    def test_sanitize_input(self):
        """Test input sanitization."""
        validator = InputValidator()
        
        malicious_input = "test\x00injection"
        sanitized = validator.sanitize_input(malicious_input)
        
        assert "\x00" not in sanitized
    
    def test_validate_schema_valid(self):
        """Test schema validation with valid data."""
        validator = InputValidator()
        
        data = {
            "location_id": "test_location",
            "prediction_time": datetime.utcnow().isoformat(),
            "context_hours": 24
        }
        
        valid, error = validator.validate_schema(data, PredictionRequest)
        
        assert valid is True
        assert error is None
    
    def test_validate_schema_invalid(self):
        """Test schema validation with invalid data."""
        validator = InputValidator()
        
        data = {
            "location_id": "",
            "prediction_time": "invalid-date",
            "context_hours": -1
        }
        
        valid, error = validator.validate_schema(data, PredictionRequest)
        
        assert valid is False
        assert error is not None


class TestAuditLogger:
    """Tests for audit logging."""
    
    def test_audit_logger_creation(self):
        """Test audit logger creation."""
        logger = AuditLogger()
        
        assert logger is not None
        assert logger.retention_days == 90
    
    def test_log_prediction_request(self):
        """Test logging prediction request."""
        logger = AuditLogger()
        
        # Should not raise
        logger.log_prediction_request(
            location_id="test_location",
            prediction_time=datetime.utcnow() + timedelta(hours=2),
            context_hours=24,
            client_id="test_client"
        )
    
    def test_log_prediction_response(self):
        """Test logging prediction response."""
        logger = AuditLogger()
        
        # Should not raise
        logger.log_prediction_response(
            location_id="test_location",
            prediction_time=datetime.utcnow() + timedelta(hours=2),
            probability=0.75,
            confidence_lower=0.65,
            confidence_upper=0.85
        )
    
    def test_log_prediction_error(self):
        """Test logging prediction error."""
        logger = AuditLogger()
        
        # Should not raise
        logger.log_prediction_error(
            location_id="test_location",
            prediction_time=datetime.utcnow() + timedelta(hours=2),
            error_type="test_error",
            error_message="Test error message"
        )
    
    def test_log_authentication_event(self):
        """Test logging authentication event."""
        logger = AuditLogger()
        
        # Should not raise
        logger.log_authentication_event(
            client_id="test_client",
            success=True,
            api_key_hash="abc123"
        )
    
    def test_log_rate_limit_event(self):
        """Test logging rate limit event."""
        logger = AuditLogger()
        
        # Should not raise
        logger.log_rate_limit_event(
            client_id="test_client",
            request_count=100,
            limit=100
        )
    
    def test_get_log_stats(self):
        """Test getting log statistics."""
        logger = AuditLogger()
        
        stats = logger.get_log_stats()
        
        assert "log_dir" in stats
        assert "retention_days" in stats
        assert "log_files" in stats
    
    def test_hash_if_sensitive(self):
        """Test sensitive data hashing."""
        logger = AuditLogger()
        
        # Sensitive value should be hashed
        result = logger._hash_if_sensitive("api_key_value")
        assert result is not None
    
    def test_sanitize_error_message(self):
        """Test error message sanitization."""
        logger = AuditLogger()
        
        # Set a test API key
        original_key = settings.api_key
        settings.api_key = "test_api_key_123"
        
        try:
            error_msg = "Error with api_key=test_api_key_123"
            sanitized = logger._sanitize_error_message(error_msg)
            
            assert "test_api_key_123" not in sanitized
        finally:
            settings.api_key = original_key
    
    def test_rotate_logs(self):
        """Test log rotation."""
        logger = AuditLogger()
        
        # Should not raise
        rotated = logger.rotate_logs()
        assert isinstance(rotated, list)
