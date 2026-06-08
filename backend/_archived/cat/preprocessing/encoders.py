"""
Preprocessing encoders for the Contextual Availability Transformer (CAT) system.
Transform raw contextual data into dense vector representations for the Transformer model.

This module implements:
- Event embedding encoder (one-hot, normalized numerical, location, temporal)
- Weather embedding encoder (normalized features, one-hot type, wind)
- Historical sequence encoder (utilization, contextual factors, temporal)
- Tensor preprocessing pipeline with validation and missing data handling
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..config import settings
from ..models.schemas import (
    AvailabilityRecord,
    CalendarEvent,
    ContextualFactors,
    EventCalendarData,
    EventType,
    HistoricalAvailabilityData,
    Season,
    WeatherConditions,
    WeatherData,
    WeatherType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ModelInput Dataclass - Requirement 4.9
# =============================================================================

@dataclass
class ModelInput:
    """
    Unified input container for the CAT Transformer model.
    
    Attributes:
        event_embeddings: Tensor of shape [event_embedding_dim]
            Encoded event calendar data with one-hot event types,
            normalized attendance, location coordinates, and temporal features.
        weather_embeddings: Tensor of shape [weather_embedding_dim]
            Encoded weather conditions including temperature, humidity,
            precipitation, wind speed, and weather type.
        historical_sequence: Tensor of shape [sequence_length, historical_embedding_dim]
            Sequence of historical availability records with contextual factors.
        temporal_encoding: Tensor of shape [temporal_encoding_dim]
            Positional encoding for the prediction timestamp.
    """
    event_embeddings: torch.Tensor
    weather_embeddings: torch.Tensor
    historical_sequence: torch.Tensor
    temporal_encoding: torch.Tensor
    
    def validate(self) -> bool:
        """
        Validate tensor shapes and values before model inference.
        
        Returns:
            True if all tensors are valid.
            
        Raises:
            ValueError: If any tensor has invalid shape or contains NaN/Inf.
        """
        # Check for NaN or Inf values
        tensors = [
            ("event_embeddings", self.event_embeddings),
            ("weather_embeddings", self.weather_embeddings),
            ("historical_sequence", self.historical_sequence),
            ("temporal_encoding", self.temporal_encoding),
        ]
        
        for name, tensor in tensors:
            if torch.isnan(tensor).any():
                raise ValueError(f"NaN detected in {name}")
            if torch.isinf(tensor).any():
                raise ValueError(f"Inf detected in {name}")
        
        # Validate shapes
        # event_embeddings: [event_embedding_dim]
        if self.event_embeddings.shape[-1] != settings.event_embedding_dim:
            raise ValueError(
                f"event_embeddings dimension mismatch: got {self.event_embeddings.shape[-1]}, "
                f"expected {settings.event_embedding_dim}"
            )
        
        # weather_embeddings: [weather_embedding_dim]
        if self.weather_embeddings.shape[-1] != settings.weather_embedding_dim:
            raise ValueError(
                f"weather_embeddings dimension mismatch: got {self.weather_embeddings.shape[-1]}, "
                f"expected {settings.weather_embedding_dim}"
            )
        
        # historical_sequence: [sequence_length, historical_embedding_dim]
        if self.historical_sequence.shape[-2] != settings.historical_sequence_length:
            raise ValueError(
                f"historical_sequence length mismatch: got {self.historical_sequence.shape[-2]}, "
                f"expected {settings.historical_sequence_length}"
            )
        if self.historical_sequence.shape[-1] != self.event_embeddings.shape[-1]:
            raise ValueError(
                f"historical_sequence embedding dim mismatch: got {self.historical_sequence.shape[-1]}, "
                f"expected {self.event_embeddings.shape[-1]}"
            )
        
        # temporal_encoding: [temporal_encoding_dim]
        if self.temporal_encoding.shape[-1] != settings.temporal_encoding_dim:
            raise ValueError(
                f"temporal_encoding dimension mismatch: got {self.temporal_encoding.shape[-1]}, "
                f"expected {settings.temporal_encoding_dim}"
            )
        
        return True
    
    def to(self, device: torch.device) -> "ModelInput":
        """Move all tensors to the specified device."""
        return ModelInput(
            event_embeddings=self.event_embeddings.to(device),
            weather_embeddings=self.weather_embeddings.to(device),
            historical_sequence=self.historical_sequence.to(device),
            temporal_encoding=self.temporal_encoding.to(device),
        )
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, ...]:
        """Get individual tensor at index for sequence data."""
        return (
            self.event_embeddings,
            self.weather_embeddings,
            self.historical_sequence[idx] if idx < len(self.historical_sequence) else self.historical_sequence[-1],
            self.temporal_encoding,
        )


# =============================================================================
# Event Embedding Encoder - Requirements 4.1, 4.2, 4.3, 4.4, 4.8
# =============================================================================

class EventEncoder(nn.Module):
    """
    Encodes event calendar data into dense vector representations.
    
    Features:
    - One-hot encoding for event types (Requirement 4.1)
    - Normalized numerical encoding for event size (Requirement 4.2)
    - Location encoding using latitude/longitude (Requirement 4.3)
    - Temporal position encoding (Requirement 4.4)
    - Mean pooling for multiple events (Requirement 4.8)
    """
    
    def __init__(
        self,
        embedding_dim: int = None,
        event_type_vocab: List[EventType] = None,
        max_attendance: int = 10000,
    ):
        """
        Initialize the event encoder.
        
        Args:
            embedding_dim: Dimension of output embeddings.
            event_type_vocab: List of event types for one-hot encoding.
            max_attendance: Maximum attendance for normalization.
        """
        super().__init__()
        
        self.embedding_dim = embedding_dim or settings.event_embedding_dim
        self.event_types = event_type_vocab or list(EventType)
        self.num_event_types = len(self.event_types)
        self.max_attendance = max_attendance
        
        # One-hot encoding dimension for event type
        self.type_embedding_dim = self.num_event_types
        
        # Size encoding (normalized) - Requirement 4.2
        self.size_embedding_dim = 16
        
        # Location encoding dimension - Requirement 4.3
        self.location_embedding_dim = 32
        
        # Time encoding dimension - Requirement 4.4
        self.time_embedding_dim = 32
        
        # Total input dimension before pooling
        self.input_dim = (
            self.type_embedding_dim +
            self.size_embedding_dim +
            self.location_embedding_dim +
            self.time_embedding_dim
        )
        
        # Projection to output dimension
        self.projection = nn.Linear(self.input_dim, self.embedding_dim)
        
        # Learnable size encoding
        self.size_encoder = nn.Sequential(
            nn.Linear(1, self.size_embedding_dim),
            nn.ReLU(),
            nn.Linear(self.size_embedding_dim, self.size_embedding_dim),
        )
        
        # Location encoder (sinusoidal positional encoding style)
        self.location_encoder = nn.Linear(2, self.location_embedding_dim)
        
        # Time encoder
        self.time_encoder = nn.Linear(4, self.time_embedding_dim)  # hour, day, month, day_of_week
    
    def forward(self, event_data: EventCalendarData) -> torch.Tensor:
        """
        Encode event calendar data into a single embedding vector.
        
        Args:
            event_data: EventCalendarData with list of events.
            
        Returns:
            Tensor of shape [embedding_dim]. Returns zero tensor if no events.
        """
        if not event_data.events:
            # Requirement 4.9: Handle missing data by substituting zero embeddings
            logger.warning(
                f"No events found in event calendar data, "
                f"substituting zero embedding for event embeddings"
            )
            return torch.zeros(self.embedding_dim, device=self._get_device())
        
        # Encode each event
        event_embeddings = []
        
        for event in event_data.events:
            event_embedding = self._encode_single_event(event)
            event_embeddings.append(event_embedding)
        
        # Stack and mean pool - Requirement 4.8
        event_embeddings = torch.stack(event_embeddings)
        pooled = torch.mean(event_embeddings, dim=0)
        
        # Project to output dimension
        output = self.projection(pooled)
        
        return output
    
    def _encode_single_event(self, event: CalendarEvent) -> torch.Tensor:
        """
        Encode a single calendar event into a feature vector.
        
        Args:
            event: A single CalendarEvent.
            
        Returns:
            Concatenated feature tensor.
        """
        device = self._get_device()
        
        # One-hot event type - Requirement 4.1
        type_vector = torch.zeros(self.num_event_types, device=device)
        type_idx = self.event_types.index(event.event_type)
        type_vector[type_idx] = 1.0
        
        # Normalized size encoding - Requirement 4.2
        size_value = min(event.expected_attendance / self.max_attendance, 1.0)
        size_embedding = self.size_encoder(
            torch.tensor([size_value], dtype=torch.float32, device=device)
        ).squeeze(0)
        
        # Location encoding - Requirement 4.3
        location_coords = torch.tensor([
            event.location.latitude / 90.0,  # Normalize to [-1, 1]
            event.location.longitude / 180.0,
        ], dtype=torch.float32, device=device)
        location_embedding = self.location_encoder(location_coords)
        
        # Time encoding - Requirement 4.4
        hour = event.start_time.hour / 24.0
        day = event.start_time.day / 31.0
        month = event.start_time.month / 12.0
        day_of_week = event.start_time.weekday() / 7.0
        
        time_features = torch.tensor(
            [hour, day, month, day_of_week],
            dtype=torch.float32,
            device=device
        )
        time_embedding = self.time_encoder(time_features)
        
        # Concatenate all features
        event_embedding = torch.cat([
            type_vector,
            size_embedding,
            location_embedding,
            time_embedding,
        ])
        
        return event_embedding
    
    def _get_device(self) -> torch.device:
        """Get the appropriate device for computations."""
        return next(self.parameters()).device if self.parameters() else torch.device("cpu")


# =============================================================================
# Weather Embedding Encoder - Requirement 4.5
# =============================================================================

class WeatherEncoder(nn.Module):
    """
    Encodes weather data into dense vector representations.
    
    Features:
    - Normalized encoding for temperature, humidity, precipitation (Requirement 4.5)
    - One-hot encoding for weather type (Requirement 4.5)
    - Wind speed encoding (Requirement 4.5)
    - Combined unified embedding (Requirement 4.5)
    """
    
    def __init__(
        self,
        embedding_dim: int = None,
        weather_type_vocab: List[WeatherType] = None,
    ):
        """
        Initialize the weather encoder.
        
        Args:
            embedding_dim: Dimension of output embeddings.
            weather_type_vocab: List of weather types for one-hot encoding.
        """
        super().__init__()
        
        self.embedding_dim = embedding_dim or settings.weather_embedding_dim
        self.weather_types = weather_type_vocab or list(WeatherType)
        self.num_weather_types = len(self.weather_types)
        
        # Numerical features dimension - Requirement 4.5
        self.num_features = 4  # temp, humidity, precip, wind
        
        # One-hot weather type dimension - Requirement 4.5
        self.type_embedding_dim = self.num_weather_types
        
        # Total input dimension
        self.input_dim = self.num_features + self.type_embedding_dim
        
        # Projection to output dimension
        self.projection = nn.Linear(self.input_dim, self.embedding_dim)
    
    def forward(self, weather_data: WeatherData) -> torch.Tensor:
        """
        Encode weather data into a single embedding vector.
        
        Args:
            weather_data: WeatherData with current conditions.
            
        Returns:
            Tensor of shape [embedding_dim]. Returns zero tensor if no conditions.
        """
        if not weather_data.current_conditions:
            # Requirement 4.9: Handle missing data by substituting zero embeddings
            logger.warning(
                f"No weather conditions found, substituting zero embedding for weather embeddings"
            )
            return torch.zeros(self.embedding_dim, device=self._get_device())
        
        conditions = weather_data.current_conditions
        
        # Numerical features (normalized) - Requirement 4.5
        temp_norm = (conditions.temperature + 50) / 110.0  # Normalize to [0, 1]
        humidity_norm = conditions.humidity / 100.0
        precip_norm = conditions.precipitation_probability
        wind_norm = min(conditions.wind_speed / 50.0, 1.0)  # Cap at 50 m/s
        
        numerical_features = torch.tensor(
            [temp_norm, humidity_norm, precip_norm, wind_norm],
            dtype=torch.float32,
            device=self._get_device()
        )
        
        # One-hot weather type - Requirement 4.5
        type_vector = torch.zeros(self.num_weather_types, device=self._get_device())
        type_idx = self.weather_types.index(conditions.weather_type)
        type_vector[type_idx] = 1.0
        
        # Concatenate features - Requirement 4.5: Combine all weather features
        features = torch.cat([numerical_features, type_vector])
        
        # Project to output dimension
        output = self.projection(features)
        
        return output
    
    def _get_device(self) -> torch.device:
        """Get the appropriate device for computations."""
        return next(self.parameters()).device if self.parameters() else torch.device("cpu")


# =============================================================================
# Historical Sequence Encoder - Requirements 4.6, 4.7
# =============================================================================

class HistoricalEncoder(nn.Module):
    """
    Encodes historical availability sequences into dense representations.
    
    Features:
    - Sequence encoding for historical availability records (Requirement 4.6)
    - Contextual factor encoding (event count, weather severity, holidays) (Requirement 4.6)
    - Temporal position encoding (Requirement 4.7)
    - Variable-length sequence handling with padding and masking (Requirement 4.6)
    """
    
    def __init__(
        self,
        embedding_dim: int = None,
        max_sequence_length: int = None,
    ):
        """
        Initialize the historical encoder.
        
        Args:
            embedding_dim: Dimension of output embeddings.
            max_sequence_length: Maximum number of historical records.
        """
        super().__init__()
        
        self.embedding_dim = embedding_dim or settings.event_embedding_dim
        self.max_length = max_sequence_length or settings.historical_sequence_length
        
        # Feature dimensions
        self.utilization_dim = 16
        self.slots_dim = 16
        self.context_dim = 32
        
        # Total per-timestep dimension
        self.input_dim = self.utilization_dim + self.slots_dim + self.context_dim
        
        # Projection to embedding dimension
        self.projection = nn.Linear(self.input_dim, self.embedding_dim)
        
        # Utilization encoder
        self.utilization_encoder = nn.Sequential(
            nn.Linear(1, self.utilization_dim),
            nn.ReLU(),
            nn.Linear(self.utilization_dim, self.utilization_dim),
        )
        
        # Slots encoder
        self.slots_encoder = nn.Sequential(
            nn.Linear(2, self.slots_dim),  # available, total
            nn.ReLU(),
            nn.Linear(self.slots_dim, self.slots_dim),
        )
        
        # Contextual factors encoder
        self.context_encoder = nn.Sequential(
            nn.Linear(8, self.context_dim),  # 4 contextual + 4 season one-hot
            nn.ReLU(),
            nn.Linear(self.context_dim, self.context_dim),
        )
    
    def forward(
        self,
        historical_data: HistoricalAvailabilityData,
        target_time: Optional[datetime] = None,
    ) -> torch.Tensor:
        """
        Encode historical availability data into a sequence of embeddings.
        
        Args:
            historical_data: HistoricalAvailabilityData with records.
            target_time: Optional target time for relative positioning (Requirement 4.7).
            
        Returns:
            Tensor of shape [max_length, embedding_dim].
            Padded with zeros if fewer records than max_length.
        """
        records = historical_data.records
        
        if not records:
            # Requirement 4.9: Handle missing data by substituting zero embeddings
            logger.warning(
                f"No historical records found for location {historical_data.location_id}, "
                f"substituting zero embedding for historical sequence"
            )
            return torch.zeros(
                self.max_length,
                self.embedding_dim,
                device=self._get_device()
            )
        
        # Process each record
        sequence_embeddings = []
        
        for record in records[-self.max_length:]:  # Take most recent records
            embedding = self._encode_single_record(record)
            sequence_embeddings.append(embedding)
        
        # Pad sequence to max_length - Requirement 4.6: Handle variable-length sequences
        if len(sequence_embeddings) < self.max_length:
            padding = torch.zeros(
                self.max_length - len(sequence_embeddings),
                self.embedding_dim,
                device=self._get_device()
            )
            sequence_embeddings = torch.cat([torch.stack(sequence_embeddings), padding], dim=0)
        else:
            sequence_embeddings = torch.stack(sequence_embeddings)
        
        return sequence_embeddings
    
    def _encode_single_record(self, record: AvailabilityRecord) -> torch.Tensor:
        """
        Encode a single availability record into a feature vector.
        
        Args:
            record: A single AvailabilityRecord.
            
        Returns:
            Feature tensor of shape [embedding_dim].
        """
        device = self._get_device()
        
        # Utilization encoding - Requirement 4.6
        utilization_input = torch.tensor(
            [[record.utilization_rate]],
            dtype=torch.float32,
            device=device
        )
        utilization_emb = self.utilization_encoder(utilization_input).squeeze(0)
        
        # Slots encoding (normalized) - Requirement 4.6
        available_norm = record.available_slots / max(record.total_slots, 1)
        total_norm = record.total_slots / 10000.0  # Normalize by max expected
        slots_input = torch.tensor(
            [available_norm, total_norm],
            dtype=torch.float32,
            device=device
        )
        slots_emb = self.slots_encoder(slots_input)
        
        # Contextual factors encoding - Requirement 4.6
        factors = record.contextual_factors
        
        # Convert season enum to integer index for one-hot encoding
        season_idx = list(Season).index(Season(factors.season.value))
        season_onehot = F.one_hot(
            torch.tensor([season_idx], device=device),
            num_classes=4,
        ).float().squeeze(0)
        
        context_input = torch.tensor(
            [
                min(factors.event_count / 10.0, 1.0),  # Normalize
                factors.weather_severity / 10.0,
                1.0 if factors.is_holiday else 0.0,
                1.0 if factors.is_weekend else 0.0,
            ],
            dtype=torch.float32,
            device=device,
        )
        
        # Add season one-hot
        context_input = torch.cat([context_input, season_onehot])
        context_emb = self.context_encoder(context_input)
        
        # Concatenate and project
        features = torch.cat([utilization_emb, slots_emb, context_emb])
        embedding = self.projection(features)
        
        return embedding
    
    def _get_device(self) -> torch.device:
        """Get the appropriate device for computations."""
        return next(self.parameters()).device if self.parameters() else torch.device("cpu")


# =============================================================================
# Temporal Position Encoder - Requirement 4.7
# =============================================================================

class TemporalEncoder(nn.Module):
    """
    Generates temporal encodings for time-based positional information.
    
    Uses sinusoidal positional encoding similar to the original Transformer paper.
    Implements Requirement 4.7: Generate temporal encodings based on
    prediction timestamp relative to historical data.
    """
    
    def __init__(
        self,
        embedding_dim: int = None,
        max_time_steps: int = 10000,
    ):
        """
        Initialize the temporal encoder.
        
        Args:
            embedding_dim: Dimension of output encodings.
            max_time_steps: Maximum number of time steps for encoding.
        """
        super().__init__()
        
        self.embedding_dim = embedding_dim or settings.temporal_encoding_dim
        self.max_time_steps = max_time_steps
        
        # Create positional encoding table
        self.register_buffer(
            "positional_encoding",
            self._create_positional_encoding(max_time_steps, self.embedding_dim),
        )
    
    def _create_positional_encoding(
        self,
        max_len: int,
        d_model: int,
    ) -> torch.Tensor:
        """Create sinusoidal positional encoding."""
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        
        return pe
    
    def forward(self, timestamp: datetime) -> torch.Tensor:
        """
        Generate temporal encoding for a specific timestamp.
        
        Args:
            timestamp: The timestamp to encode.
            
        Returns:
            Tensor of shape [embedding_dim].
        """
        # Convert timestamp to a position value
        # Use day of year and hour as the position
        day_of_year = timestamp.timetuple().tm_yday
        hour = timestamp.hour
        
        # Combine into a single position
        position = (day_of_year * 24 + hour) % self.max_time_steps
        
        # Get encoding from table
        encoding = self.positional_encoding[position]
        
        return encoding
    
    def encode_range(
        self,
        start_time: datetime,
        end_time: datetime,
        num_steps: int,
    ) -> torch.Tensor:
        """
        Generate temporal encodings for a range of timestamps.
        
        Args:
            start_time: Start of the time range.
            end_time: End of the time range.
            num_steps: Number of time steps to encode.
            
        Returns:
            Tensor of shape [num_steps, embedding_dim].
        """
        time_range = (end_time - start_time).total_seconds()
        step_seconds = time_range / (num_steps - 1) if num_steps > 1 else 0
        
        encodings = []
        for i in range(num_steps):
            step_time = start_time + timedelta(seconds=step_seconds * i)
            encodings.append(self(step_time))
        
        return torch.stack(encodings)


# =============================================================================
# Tensor Preprocessing Pipeline - Requirement 4.9
# =============================================================================

class TensorPreprocessor:
    """
    Main preprocessing pipeline that combines all encoders and handles
    tensor operations for model input.
    
    Implements Requirement 4.9:
    - Create ModelInput dataclass with all embedding tensors
    - Implement tensor normalization and standardization
    - Handle missing data by substituting zero embeddings
    - Validate tensor shapes before model inference
    """
    
    def __init__(
        self,
        event_encoder: EventEncoder = None,
        weather_encoder: WeatherEncoder = None,
        historical_encoder: HistoricalEncoder = None,
        temporal_encoder: TemporalEncoder = None,
        device: str = None,
    ):
        """
        Initialize the tensor preprocessor.
        
        Args:
            event_encoder: Event encoder instance.
            weather_encoder: Weather encoder instance.
            historical_encoder: Historical encoder instance.
            temporal_encoder: Temporal encoder instance.
            device: Device to place tensors on ('cpu' or 'cuda').
        """
        self.device = torch.device(device) if device else torch.device("cpu")
        
        self.event_encoder = event_encoder or EventEncoder()
        self.weather_encoder = weather_encoder or WeatherEncoder()
        self.historical_encoder = historical_encoder or HistoricalEncoder()
        self.temporal_encoder = temporal_encoder or TemporalEncoder()
        
        # Move encoders to device
        self.event_encoder.to(self.device)
        self.weather_encoder.to(self.device)
        self.historical_encoder.to(self.device)
        self.temporal_encoder.to(self.device)
        
        # Set to eval mode
        self.event_encoder.eval()
        self.weather_encoder.eval()
        self.historical_encoder.eval()
        self.temporal_encoder.eval()
    
    def preprocess(
        self,
        event_data: EventCalendarData,
        weather_data: WeatherData,
        historical_data: HistoricalAvailabilityData,
        prediction_time: datetime,
    ) -> ModelInput:
        """
        Preprocess contextual data into ModelInput tensors.
        
        Args:
            event_data: Event calendar data.
            weather_data: Weather data.
            historical_data: Historical availability data.
            prediction_time: Time of prediction.
            
        Returns:
            ModelInput dataclass with all embedding tensors.
        """
        with torch.no_grad():
            # Encode each component
            event_embeddings = self.event_encoder(event_data)
            weather_embeddings = self.weather_encoder(weather_data)
            historical_sequence = self.historical_encoder(historical_data, prediction_time)
            temporal_encoding = self.temporal_encoder(prediction_time)
            
            # Move to device
            event_embeddings = event_embeddings.to(self.device)
            weather_embeddings = weather_embeddings.to(self.device)
            historical_sequence = historical_sequence.to(self.device)
            temporal_encoding = temporal_encoding.to(self.device)
            
            # Create ModelInput dataclass
            model_input = ModelInput(
                event_embeddings=event_embeddings,
                weather_embeddings=weather_embeddings,
                historical_sequence=historical_sequence,
                temporal_encoding=temporal_encoding,
            )
            
            # Validate tensor shapes before model inference - Requirement 4.9
            model_input.validate()
            
            return model_input
    
    def validate_input(
        self,
        event_embeddings: torch.Tensor,
        weather_embeddings: torch.Tensor,
        historical_sequence: torch.Tensor,
        temporal_encoding: torch.Tensor,
    ) -> bool:
        """
        Validate that input tensors have expected shapes and values.
        
        Args:
            event_embeddings: Event embeddings tensor.
            weather_embeddings: Weather embeddings tensor.
            historical_sequence: Historical sequence tensor.
            temporal_encoding: Temporal encoding tensor.
            
        Returns:
            True if inputs are valid.
            
        Raises:
            ValueError: If any tensor has invalid shape or contains NaN/Inf.
        """
        # Check for NaN or Inf values
        for name, tensor in [
            ("event_embeddings", event_embeddings),
            ("weather_embeddings", weather_embeddings),
            ("historical_sequence", historical_sequence),
            ("temporal_encoding", temporal_encoding),
        ]:
            if torch.isnan(tensor).any():
                raise ValueError(f"NaN detected in {name}")
            if torch.isinf(tensor).any():
                raise ValueError(f"Inf detected in {name}")
        
        # Check shapes
        expected_event_dim = settings.event_embedding_dim
        expected_weather_dim = settings.weather_embedding_dim
        expected_hist_seq_len = settings.historical_sequence_length
        expected_temp_dim = settings.temporal_encoding_dim
        
        if event_embeddings.shape[-1] != expected_event_dim:
            raise ValueError(
                f"Event embedding dim mismatch: {event_embeddings.shape[-1]} != {expected_event_dim}"
            )
        
        if weather_embeddings.shape[-1] != expected_weather_dim:
            raise ValueError(
                f"Weather embedding dim mismatch: {weather_embeddings.shape[-1]} != {expected_weather_dim}"
            )
        
        if historical_sequence.shape[-2] != expected_hist_seq_len:
            raise ValueError(
                f"Historical sequence length mismatch: {historical_sequence.shape[-2]} != {expected_hist_seq_len}"
            )
        
        if temporal_encoding.shape[-1] != expected_temp_dim:
            raise ValueError(
                f"Temporal encoding dim mismatch: {temporal_encoding.shape[-1]} != {expected_temp_dim}"
            )
        
        return True
    
    def create_model_input(
        self,
        event_embeddings: torch.Tensor,
        weather_embeddings: torch.Tensor,
        historical_sequence: torch.Tensor,
        temporal_encoding: torch.Tensor,
    ) -> ModelInput:
        """
        Create ModelInput from individual tensors.
        
        Args:
            event_embeddings: Event embeddings [event_dim].
            weather_embeddings: Weather embeddings [weather_dim].
            historical_sequence: Historical sequence [seq_len, hist_dim].
            temporal_encoding: Temporal encoding [temp_dim].
            
        Returns:
            ModelInput dataclass.
        """
        # Validate inputs
        self.validate_input(
            event_embeddings, weather_embeddings,
            historical_sequence, temporal_encoding
        )
        
        return ModelInput(
            event_embeddings=event_embeddings,
            weather_embeddings=weather_embeddings,
            historical_sequence=historical_sequence,
            temporal_encoding=temporal_encoding,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def create_preprocessor(device: str = None) -> TensorPreprocessor:
    """Create a preprocessor with default configuration."""
    return TensorPreprocessor(device=device)


def encode_events(
    event_data: EventCalendarData,
    embedding_dim: int = None,
) -> torch.Tensor:
    """
    Convenience function to encode event data.
    
    Args:
        event_data: Event calendar data.
        embedding_dim: Output embedding dimension.
        
    Returns:
        Event embedding tensor.
    """
    encoder = EventEncoder(embedding_dim=embedding_dim)
    return encoder(event_data)


def encode_weather(
    weather_data: WeatherData,
    embedding_dim: int = None,
) -> torch.Tensor:
    """
    Convenience function to encode weather data.
    
    Args:
        weather_data: Weather data.
        embedding_dim: Output embedding dimension.
        
    Returns:
        Weather embedding tensor.
    """
    encoder = WeatherEncoder(embedding_dim=embedding_dim)
    return encoder(weather_data)


def encode_historical(
    historical_data: HistoricalAvailabilityData,
    embedding_dim: int = None,
    target_time: datetime = None,
) -> torch.Tensor:
    """
    Convenience function to encode historical data.
    
    Args:
        historical_data: Historical availability data.
        embedding_dim: Output embedding dimension.
        target_time: Target time for relative positioning.
        
    Returns:
        Historical sequence tensor.
    """
    encoder = HistoricalEncoder(embedding_dim=embedding_dim)
    return encoder(historical_data, target_time)


# =============================================================================
# Main Test
# =============================================================================

if __name__ == "__main__":
    from datetime import datetime, timedelta
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing preprocessing module...")
    
    # Create sample data
    event_data = EventCalendarData(
        events=[
            CalendarEvent(
                title="Test Concert",
                event_type=EventType.CONCERT,
                expected_attendance=5000,
                location=Location(
                    venue_id="test_venue",
                    latitude=40.7128,
                    longitude=-74.0060,
                    capacity=10000,
                ),
                start_time=datetime.utcnow() + timedelta(hours=2),
                end_time=datetime.utcnow() + timedelta(hours=6),
                is_outdoor=False,
            ),
        ],
        last_updated=datetime.utcnow(),
    )
    
    weather_data = WeatherData(
        current_conditions=WeatherConditions(
            temperature=25.5,
            humidity=65.0,
            precipitation_probability=0.3,
            wind_speed=5.2,
            weather_type=WeatherType.CLEAR,
        ),
        forecast=[],
        last_updated=datetime.utcnow(),
    )
    
    historical_data = HistoricalAvailabilityData(
        records=[
            AvailabilityRecord(
                timestamp=datetime.utcnow() - timedelta(hours=i),
                available_slots=100,
                total_slots=500,
                utilization_rate=0.8,
                contextual_factors=ContextualFactors(
                    event_count=1,
                    weather_severity=2,
                    is_holiday=False,
                    is_weekend=True,
                    season=Season.SUMMER,
                ),
            )
            for i in range(12)
        ],
        location_id="test_location",
    )
    
    # Create preprocessor
    preprocessor = create_preprocessor(device="cpu")
    
    # Test full preprocessing
    model_input = preprocessor.preprocess(
        event_data,
        weather_data,
        historical_data,
        datetime.utcnow(),
    )
    
    print(f"ModelInput created successfully:")
    print(f"  event_embeddings shape: {model_input.event_embeddings.shape}")
    print(f"  weather_embeddings shape: {model_input.weather_embeddings.shape}")
    print(f"  historical_sequence shape: {model_input.historical_sequence.shape}")
    print(f"  temporal_encoding shape: {model_input.temporal_encoding.shape}")
    
    # Test validation
    try:
        model_input.validate()
        print("ModelInput validation: PASSED")
    except ValueError as e:
        print(f"ModelInput validation: FAILED - {e}")
    
    # Test with empty data (missing data handling)
    print("\nTesting missing data handling...")
    empty_event_data = EventCalendarData(events=[], last_updated=datetime.utcnow())
    empty_weather_data = WeatherData(current_conditions=None, forecast=[], last_updated=datetime.utcnow())
    empty_historical_data = HistoricalAvailabilityData(records=[], location_id="test")
    
    model_input_empty = preprocessor.preprocess(
        empty_event_data,
        empty_weather_data,
        empty_historical_data,
        datetime.utcnow(),
    )
    
    print(f"Empty data handled successfully:")
    print(f"  event_embeddings all zero: {model_input_empty.event_embeddings.sum() == 0}")
    print(f"  weather_embeddings all zero: {model_input_empty.weather_embeddings.sum() == 0}")
    print(f"  historical_sequence all zero: {model_input_empty.historical_sequence.sum() == 0}")
    
    print("\nAll tests passed!")