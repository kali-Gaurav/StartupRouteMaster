"""
Configuration management for the Contextual Availability Transformer (CAT) system.
Uses Pydantic settings for environment-based configuration.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class CatSettings(BaseSettings):
    """Main configuration settings for the CAT system."""
    
    # Model Configuration
    model_name: str = "cat-v1"
    model_version: str = "1.0.0"
    model_dim: int = 256
    num_layers: int = 4
    num_attention_heads: int = 8
    feedforward_dim: int = 1024
    dropout_rate: float = 0.1
    
    # Embedding Dimensions
    event_embedding_dim: int = 64
    weather_embedding_dim: int = 32
    historical_sequence_length: int = 24
    temporal_encoding_dim: int = 64
    
    # Railway-specific Dimensions
    station_heuristic_dim: int = 128
    journey_dna_dim: int = 64
    num_train_classes: int = 4
    
    # Training Configuration
    learning_rate: float = 1e-4
    weight_decay: float = 0.01
    batch_size: int = 32
    max_epochs: int = 100
    early_stopping_patience: int = 10
    warmup_steps: int = 1000
    gradient_accumulation_steps: int = 1
    
    # Data Configuration
    context_window_hours: int = 24
    prediction_horizon_hours: int = 24
    min_training_window_days: int = 180
    train_split_ratio: float = 0.8
    val_split_ratio: float = 0.1
    test_split_ratio: float = 0.1
    
    # Performance Configuration
    inference_batch_size: int = 16
    max_concurrent_requests: int = 100
    prediction_cache_ttl_seconds: int = 300
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    cors_origins: List[str] = ["*"]
    
    # CAT Service URL (for client)
    api_url: Optional[str] = None
    
    # External API Configuration (for real API integration)
    event_api_url: Optional[str] = None
    event_api_key: Optional[str] = None
    weather_api_url: Optional[str] = None
    weather_api_key: Optional[str] = None
    event_api_timeout_seconds: int = 30
    weather_api_timeout_seconds: int = 30
    max_retries: int = 3
    
    # Database Configuration
    database_url: Optional[str] = None
    historical_records_table: str = "availability_records"
    
    # Redis Configuration (for caching)
    redis_url: Optional[str] = None
    redis_cache_prefix: str = "cat:"
    
    # Security Configuration
    api_key: Optional[str] = None
    rate_limit_requests_per_minute: int = 100
    enable_tls: bool = False
    
    # Monitoring Configuration
    log_level: str = "INFO"
    metrics_enabled: bool = True
    prometheus_port: int = 9090
    
    # Synthetic Data Configuration
    use_synthetic_data: bool = True
    synthetic_data_size: int = 1000000
    synthetic_num_locations: int = 100
    synthetic_start_date: str = "2023-01-01"
    synthetic_end_date: str = "2024-06-01"
    
    model_config = SettingsConfigDict(
        env_prefix="CAT_",
        env_file=".env",
        extra="ignore"
    )


# Global settings instance
settings = CatSettings()


def get_settings() -> CatSettings:
    """Get the current settings instance."""
    return settings


def update_settings(**kwargs) -> None:
    """Update settings with new values."""
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)