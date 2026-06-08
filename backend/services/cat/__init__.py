# Contextual Availability Transformer (CAT)

"""
Contextual Availability Transformer (CAT) - ML system for availability prediction.

This package provides:
- Data collection from external APIs (event calendar, weather, historical)
- Preprocessing module for contextual data encoding
- Transformer-based ML model for availability prediction
- Inference service with low-latency predictions
- Training pipeline for model development
"""

from .data_models import (
    ContextualData,
    EventCalendarData,
    WeatherData,
    HistoricalAvailabilityData,
    AvailabilityPrediction,
    ModelInput,
)

from .data_collector import DataCollector
from .preprocessing import PreprocessingModule
from .model import CATModel
from .inference_service import InferenceService
from .training_pipeline import TrainingPipeline

__all__ = [
    'ContextualData',
    'EventCalendarData',
    'WeatherData',
    'HistoricalAvailabilityData',
    'AvailabilityPrediction',
    'ModelInput',
    'DataCollector',
    'PreprocessingModule',
    'CATModel',
    'InferenceService',
    'TrainingPipeline',
]