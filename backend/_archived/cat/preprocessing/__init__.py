"""Preprocessing module for CAT.

This module provides encoders for transforming raw contextual data
(event calendar, weather, historical availability) into dense vector
representations suitable for the CAT Transformer model.

Classes:
    - ModelInput: Unified input dataclass for the Transformer model
    - EventEncoder: Encodes event calendar data with one-hot, normalized, and positional features
    - WeatherEncoder: Encodes weather conditions with normalized features and one-hot types
    - HistoricalEncoder: Encodes historical availability sequences with contextual factors
    - TemporalEncoder: Generates sinusoidal temporal position encodings
    - TensorPreprocessor: Main pipeline combining all encoders with validation
"""

from .encoders import (
    EventEncoder,
    WeatherEncoder,
    HistoricalEncoder,
    TemporalEncoder,
    TensorPreprocessor,
    ModelInput,
    create_preprocessor,
    encode_events,
    encode_weather,
    encode_historical,
)

__all__ = [
    "EventEncoder",
    "WeatherEncoder",
    "HistoricalEncoder",
    "TemporalEncoder",
    "TensorPreprocessor",
    "ModelInput",
    "create_preprocessor",
    "encode_events",
    "encode_weather",
    "encode_historical",
]