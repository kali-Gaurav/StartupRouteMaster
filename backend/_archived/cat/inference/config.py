"""
Inference service configuration for the Contextual Availability Transformer (CAT) system.
Uses Pydantic settings for environment-based configuration.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class InferenceSettings(BaseSettings):
    """Configuration settings for the CAT inference service."""
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    debug: bool = False
    
    # CORS Configuration
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_request_enabled: bool = True
    log_response_enabled: bool = True
    log_request_timing: bool = True
    
    # Monitoring Configuration
    metrics_enabled: bool = True
    prometheus_port: int = 9090
    
    # Health Check Configuration
    health_check_interval_seconds: int = 30
    readiness_check_timeout_seconds: int = 5
    
    # Model Configuration
    model_path: str = "checkpoints/best_model.pt"
    model_warmup_requests: int = 5
    
    # Cache Configuration
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    local_cache_ttl_seconds: int = 60
    
    # Rate Limiting Configuration
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 100
    
    # Request Configuration
    max_request_size_bytes: int = 1048576  # 1MB
    max_batch_predictions: int = 100
    
    # Streaming Configuration
    streaming_enabled: bool = True
    streaming_default_interval_seconds: int = 60
    streaming_max_interval_seconds: int = 3600
    streaming_default_duration_seconds: int = 3600
    streaming_max_duration_seconds: int = 86400
    streaming_heartbeat_interval_seconds: int = 30
    streaming_max_locations_per_stream: int = 10
    
    model_config = SettingsConfigDict(
        env_prefix="CAT_INFERENCE_",
        env_file=".env",
        extra="ignore"
    )


# Global settings instance
inference_settings = InferenceSettings()


def get_inference_settings() -> InferenceSettings:
    """Get the current inference settings instance."""
    return inference_settings


def update_inference_settings(**kwargs) -> None:
    """Update inference settings with new values."""
    for key, value in kwargs.items():
        if hasattr(inference_settings, key):
            setattr(inference_settings, key, value)