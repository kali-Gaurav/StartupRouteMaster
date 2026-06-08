"""
Preprocessing Module for CAT.

This module transforms raw contextual data into model-ready tensors:
- Event embeddings
- Weather embeddings
- Historical sequence encoding
- Temporal encodings
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
import logging

from .data_models import (
    ContextualData,
    EventCalendarData,
    WeatherData,
    HistoricalAvailabilityData,
    ModelInput,
)

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing."""
    event_embedding_dim: int = 128
    weather_embedding_dim: int = 64
    historical_sequence_length: int = 24
    temporal_encoding_dim: int = 32
    max_events: int = 10


class EventEncoder:
    """Encodes event data into embeddings."""
    
    def __init__(self, embedding_dim: int = 128):
        self.embedding_dim = embedding_dim
        self.event_type_vocab = ['CONCERT', 'SPORTS', 'CONFERENCE', 'FESTIVAL', 'CONVENTION', 'HOLIDAY', 'OTHER']
    
    def encode_events(self, event_data: EventCalendarData) -> List[float]:
        """
        Encode event data into embeddings.
        
        Args:
            event_data: EventCalendarData with events
            
        Returns:
            List of floats representing event embeddings
        """
        if not event_data.events:
            return [0.0] * self.embedding_dim
        
        event_vectors = []
        
        for event in event_data.events[:10]:  # Limit to max_events
            event_vector = self._encode_single_event(event)
            event_vectors.append(event_vector)
        
        # Mean pooling
        if event_vectors:
            pooled = np.mean(event_vectors, axis=0)
            return pooled.tolist()
        else:
            return [0.0] * self.embedding_dim
    
    def _encode_single_event(self, event) -> np.ndarray:
        """Encode a single event into a vector."""
        # Event type one-hot encoding
        type_vector = np.zeros(len(self.event_type_vocab))
        try:
            type_idx = self.event_type_vocab.index(event.event_type.value)
            type_vector[type_idx] = 1.0
        except ValueError:
            pass
        
        # Event size encoding (normalized)
        size_vector = np.array([min(event.expected_attendance / 10000, 1.0)])
        
        # Location encoding (normalized lat/lon)
        location_vector = np.array([
            (event.location.latitude + 90) / 180,
            (event.location.longitude + 180) / 360,
        ])
        
        # Time encoding (temporal position)
        time_vector = self._encode_time(event.start_time)
        
        # Concatenate all vectors
        vector = np.concatenate([type_vector, size_vector, location_vector, time_vector])
        
        # Pad or truncate to embedding_dim
        if len(vector) < self.embedding_dim:
            vector = np.pad(vector, (0, self.embedding_dim - len(vector)))
        else:
            vector = vector[:self.embedding_dim]
        
        return vector
    
    def _encode_time(self, dt: datetime) -> np.ndarray:
        """Encode datetime into temporal position encoding."""
        # Hour of day (normalized)
        hour = np.array([dt.hour / 24])
        
        # Day of week (one-hot)
        day_of_week = np.zeros(7)
        day_of_week[dt.weekday()] = 1.0
        
        # Month (normalized)
        month = np.array([dt.month / 12])
        
        return np.concatenate([hour, day_of_week, month])


class WeatherEncoder:
    """Encodes weather data into embeddings."""
    
    def __init__(self, embedding_dim: int = 64):
        self.embedding_dim = embedding_dim
        self.weather_type_vocab = ['CLEAR', 'CLOUDY', 'RAIN', 'SNOW', 'STORM', 'FOG', 'WINDY']
    
    def encode_weather(self, weather_data: WeatherData) -> List[float]:
        """
        Encode weather data into embeddings.
        
        Args:
            weather_data: WeatherData with current conditions
            
        Returns:
            List of floats representing weather embeddings
        """
        current = weather_data.current_conditions
        
        # Temperature (normalized to [-1, 1])
        temp = np.array([(current.temperature + 50) / 110 * 2 - 1])
        
        # Humidity (normalized)
        humidity = np.array([current.humidity / 100])
        
        # Precipitation probability
        precip = np.array([current.precipitation_probability])
        
        # Wind speed (normalized)
        wind = np.array([min(current.wind_speed / 100, 1.0)])
        
        # Weather type one-hot
        weather_type = np.zeros(len(self.weather_type_vocab))
        try:
            type_idx = self.weather_type_vocab.index(current.weather_type.value)
            weather_type[type_idx] = 1.0
        except ValueError:
            pass
        
        # Concatenate all vectors
        vector = np.concatenate([temp, humidity, precip, wind, weather_type])
        
        # Pad or truncate to embedding_dim
        if len(vector) < self.embedding_dim:
            vector = np.pad(vector, (0, self.embedding_dim - len(vector)))
        else:
            vector = vector[:self.embedding_dim]
        
        return vector.tolist()


class HistoricalEncoder:
    """Encodes historical availability data into sequences."""
    
    def __init__(self, sequence_length: int = 24):
        self.sequence_length = sequence_length
    
    def encode_historical(self, historical_data: HistoricalAvailabilityData) -> List[float]:
        """
        Encode historical availability data into sequence.
        
        Args:
            historical_data: HistoricalAvailabilityData with records
            
        Returns:
            List of floats representing historical sequence
        """
        if not historical_data.records:
            return [0.0] * (self.sequence_length * 5)
        
        # Sort records by timestamp
        records = sorted(historical_data.records, key=lambda r: r.timestamp, reverse=True)
        
        # Take most recent records
        records = records[:self.sequence_length]
        
        # Encode each record
        sequence = []
        for record in records:
            record_vector = self._encode_record(record)
            sequence.extend(record_vector)
        
        # Pad with zeros if needed
        while len(sequence) < self.sequence_length * 5:
            sequence.extend([0.0] * 5)
        
        # Truncate if needed
        sequence = sequence[:self.sequence_length * 5]
        
        return sequence
    
    def _encode_record(self, record) -> List[float]:
        """Encode a single availability record."""
        # Utilization rate
        utilization = [record.utilization_rate]
        
        # Event count (normalized)
        event_count = [min(record.contextual_factors.event_count / 10, 1.0)]
        
        # Weather severity (normalized)
        weather_severity = [record.contextual_factors.weather_severity / 5]
        
        # Is holiday (binary)
        is_holiday = [1.0 if record.contextual_factors.is_holiday else 0.0]
        
        # Is weekend (binary)
        is_weekend = [1.0 if record.contextual_factors.is_weekend else 0.0]
        
        return utilization + event_count + weather_severity + is_holiday + is_weekend


class TemporalEncoder:
    """Generates temporal encodings for predictions."""
    
    def __init__(self, encoding_dim: int = 32):
        self.encoding_dim = encoding_dim
    
    def generate_temporal_encoding(self, prediction_time: datetime, history_window: int = 24) -> List[float]:
        """
        Generate temporal encoding for prediction time.
        
        Args:
            prediction_time: Time for prediction
            history_window: Hours of history to consider
            
        Returns:
            List of floats representing temporal encoding
        """
        # Current time
        now = datetime.now()
        hours_until_prediction = (prediction_time - now).total_seconds() / 3600
        
        # Hours since start of day
        hours_since_midnight = prediction_time.hour + prediction_time.minute / 60
        
        # Day of week (one-hot)
        day_of_week = np.zeros(7)
        day_of_week[prediction_time.weekday()] = 1.0
        
        # Month (normalized)
        month = np.array([prediction_time.month / 12])
        
        # Is weekend (binary)
        is_weekend = np.array([1.0 if prediction_time.weekday() >= 5 else 0.0])
        
        # Is holiday (placeholder - would need holiday calendar)
        is_holiday = np.array([0.0])
        
        # Hours until prediction (normalized)
        hours_until = np.array([min(hours_until_prediction / 24, 1.0)])
        
        # Hours since midnight (normalized)
        hours_since = np.array([hours_since_midnight / 24])
        
        # Concatenate all vectors
        vector = np.concatenate([
            hours_until,
            hours_since,
            day_of_week,
            month,
            is_weekend,
            is_holiday,
        ])
        
        # Pad or truncate to encoding_dim
        if len(vector) < self.encoding_dim:
            vector = np.pad(vector, (0, self.encoding_dim - len(vector)))
        else:
            vector = vector[:self.encoding_dim]
        
        return vector.tolist()


class PreprocessingModule:
    """
    Preprocessing module that transforms contextual data into model inputs.
    
    Combines all encoders to create ModelInput tensors.
    """
    
    def __init__(self, config: PreprocessingConfig = None):
        """
        Initialize the preprocessing module.
        
        Args:
            config: PreprocessingConfig with encoding parameters
        """
        self.config = config or PreprocessingConfig()
        
        self.event_encoder = EventEncoder(self.config.event_embedding_dim)
        self.weather_encoder = WeatherEncoder(self.config.weather_embedding_dim)
        self.historical_encoder = HistoricalEncoder(self.config.historical_sequence_length)
        self.temporal_encoder = TemporalEncoder(self.config.temporal_encoding_dim)
    
    def preprocess_contextual_data(self, contextual_data: ContextualData) -> ModelInput:
        """
        Preprocess contextual data into model input.
        
        Args:
            contextual_data: ContextualData with all fetched data
            
        Returns:
            ModelInput with encoded tensors
        """
        logger.info("Preprocessing contextual data")
        
        # Encode each component
        event_embeddings = self.event_encoder.encode_events(contextual_data.event_calendar)
        weather_embeddings = self.weather_encoder.encode_weather(contextual_data.weather)
        historical_sequence = self.historical_encoder.encode_historical(contextual_data.historical_availability)
        
        # Generate temporal encoding
        temporal_encoding = self.temporal_encoder.generate_temporal_encoding(
            prediction_time=datetime.now(),
            history_window=self.config.historical_sequence_length
        )
        
        model_input = ModelInput(
            event_embeddings=event_embeddings,
            weather_embeddings=weather_embeddings,
            historical_sequence=historical_sequence,
            temporal_encoding=temporal_encoding,
        )
        
        logger.info(f"Preprocessing complete. Input dimensions: "
                   f"event={len(event_embeddings)}, "
                   f"weather={len(weather_embeddings)}, "
                   f"historical={len(historical_sequence)}, "
                   f"temporal={len(temporal_encoding)}")
        
        return model_input
    
    def validate_model_input(self, model_input: ModelInput) -> bool:
        """
        Validate model input dimensions.
        
        Args:
            model_input: ModelInput to validate
            
        Returns:
            True if valid, False otherwise
        """
        expected_dims = {
            'event_embeddings': self.config.event_embedding_dim,
            'weather_embeddings': self.config.weather_embedding_dim,
            'historical_sequence': self.config.historical_sequence_length * 5,
            'temporal_encoding': self.config.temporal_encoding_dim,
        }
        
        for field, expected_dim in expected_dims.items():
            actual_dim = len(getattr(model_input, field))
            if actual_dim != expected_dim:
                logger.error(f"Invalid dimension for {field}: expected {expected_dim}, got {actual_dim}")
                return False
        
        return True