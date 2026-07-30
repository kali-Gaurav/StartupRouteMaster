"""
Models module for the Contextual Availability Transformer (CAT) system.

This module contains the complete Transformer model architecture including:
- Multi-head attention mechanism
- Feed-forward network layers
- Transformer encoder layers and stacks
- Prediction heads with confidence intervals
- Complete CAT model class

All components follow the design specifications and support:
- Configurable model dimensions and layer counts
- Attention weight extraction for interpretability
- Variable-length sequence handling
- Production-ready type hints and error handling
"""

from .attention import (
    MultiHeadAttention
)

from .feed_forward import (
    FeedForwardNetwork
)

from .encoder import (
    TransformerEncoderLayer,
    TransformerEncoder
)

from .prediction_head import (
    PredictionHead,
    ConfidenceIntervalEstimator
)

from .transformer import (
    CATModel,
    ModelConfig,
    create_cat_model,
    create_tiny_model,
    create_large_model
)

from .schemas import (
    EventType,
    WeatherType,
    Season,
    TrainClass,
    Location,
    CalendarEvent,
    EventCalendarData,
    WeatherConditions,
    WeatherForecast,
    WeatherData,
    ContextualFactors,
    AvailabilityRecord,
    HistoricalAvailabilityData,
    ContextualData,
    ContributingFactor,
    AvailabilityPrediction,
    RailwayAvailabilityPrediction,
    PredictionRequest,
    BatchPredictionRequest,
    BatchPredictionResponse,
    HealthStatus,
    ServiceHealth,
    LocationInfo,
    LocationListResponse
)

__all__ = [
    # Attention
    "MultiHeadAttention",
    
    # Feed-forward
    "FeedForwardNetwork",
    
    # Encoder
    "TransformerEncoderLayer",
    "TransformerEncoder",
    
    # Prediction head
    "PredictionHead",
    "ConfidenceIntervalEstimator",
    
    # Main model
    "CATModel",
    "ModelConfig",
    "create_cat_model",
    "create_tiny_model",
    "create_large_model",
    
    # Schemas
    "EventType",
    "WeatherType",
    "Season",
    "TrainClass",
    "Location",
    "CalendarEvent",
    "EventCalendarData",
    "WeatherConditions",
    "WeatherForecast",
    "WeatherData",
    "ContextualFactors",
    "AvailabilityRecord",
    "HistoricalAvailabilityData",
    "ContextualData",
    "ContributingFactor",
    "AvailabilityPrediction",
    "RailwayAvailabilityPrediction",
    "PredictionRequest",
    "BatchPredictionRequest",
    "BatchPredictionResponse",
    "HealthStatus",
    "ServiceHealth",
    "LocationInfo",
    "LocationListResponse"
]