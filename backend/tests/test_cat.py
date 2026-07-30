"""
Tests for Contextual Availability Transformer (CAT).

Tests all components:
- Data models
- Data collector
- Preprocessing module
- Transformer model
- Inference service
"""

import pytest
import torch
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any

from backend.services.cat.data_models import (
    ContextualData,
    EventCalendarData,
    WeatherData,
    HistoricalAvailabilityData,
    AvailabilityPrediction,
    ModelInput,
    CalendarEvent,
    EventCalendarData,
    WeatherConditions,
    WeatherForecast,
    AvailabilityRecord,
    ContextualFactors,
    Location,
    EventType,
    WeatherType,
    Season,
)


class TestDataModels:
    """Tests for data models."""
    
    def test_location_model(self):
        """Test Location model validation."""
        location = Location(
            venue_id="venue-001",
            latitude=28.6421,
            longitude=77.2195,
            capacity=10000,
        )
        
        assert location.venue_id == "venue-001"
        assert location.latitude == 28.6421
        assert location.longitude == 77.2195
        assert location.capacity == 10000
    
    def test_calendar_event_model(self):
        """Test CalendarEvent model validation."""
        location = Location(
            venue_id="venue-001",
            latitude=28.6421,
            longitude=77.2195,
            capacity=10000,
        )
        
        event = CalendarEvent(
            event_id="event-001",
            title="Concert",
            event_type=EventType.CONCERT,
            expected_attendance=5000,
            location=location,
            start_time=datetime(2026, 5, 15, 18, 0, 0),
            end_time=datetime(2026, 5, 15, 22, 0, 0),
            is_outdoor=True,
        )
        
        assert event.event_id == "event-001"
        assert event.title == "Concert"
        assert event.event_type == EventType.CONCERT
        assert event.expected_attendance == 5000
        assert event.is_outdoor is True
    
    def test_weather_conditions_model(self):
        """Test WeatherConditions model validation."""
        conditions = WeatherConditions(
            temperature=25.5,
            humidity=60.0,
            precipitation_probability=0.2,
            wind_speed=10.0,
            weather_type=WeatherType.CLEAR,
        )
        
        assert conditions.temperature == 25.5
        assert conditions.humidity == 60.0
        assert conditions.precipitation_probability == 0.2
        assert conditions.wind_speed == 10.0
        assert conditions.weather_type == WeatherType.CLEAR
    
    def test_availability_record_model(self):
        """Test AvailabilityRecord model validation."""
        factors = ContextualFactors(
            event_count=2,
            weather_severity=2,
            is_holiday=False,
            is_weekend=True,
            season=Season.SUMMER,
        )
        
        record = AvailabilityRecord(
            timestamp=datetime(2026, 5, 15, 10, 0, 0),
            available_slots=50,
            total_slots=100,
            utilization_rate=0.5,
            contextual_factors=factors,
        )
        
        assert record.available_slots == 50
        assert record.total_slots == 100
        assert record.utilization_rate == 0.5
        assert record.contextual_factors.event_count == 2
    
    def test_availability_prediction_model(self):
        """Test AvailabilityPrediction model validation."""
        prediction = AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[
                ("event_calendar", 0.3),
                ("weather", 0.3),
                ("historical", 0.3),
                ("temporal", 0.1),
            ],
        )
        
        assert prediction.probability == 0.75
        assert prediction.confidence_interval == (0.65, 0.85)
        assert len(prediction.contributing_factors) == 4


class TestPreprocessing:
    """Tests for preprocessing module."""
    
    def test_event_encoder(self):
        """Test event encoding."""
        from backend.services.cat.preprocessing import EventEncoder
        
        encoder = EventEncoder(embedding_dim=128)
        
        # Test with no events
        event_data = EventCalendarData(events=[])
        embedding = encoder.encode_events(event_data)
        
        assert len(embedding) == 128
        assert all(x == 0.0 for x in embedding)
    
    def test_weather_encoder(self):
        """Test weather encoding."""
        from backend.services.cat.preprocessing import WeatherEncoder
        
        encoder = WeatherEncoder(embedding_dim=64)
        
        conditions = WeatherConditions(
            temperature=25.0,
            humidity=60.0,
            precipitation_probability=0.1,
            wind_speed=10.0,
            weather_type=WeatherType.CLEAR,
        )
        
        weather_data = WeatherData(current_conditions=conditions)
        embedding = encoder.encode_weather(weather_data)
        
        assert len(embedding) == 64
    
    def test_temporal_encoder(self):
        """Test temporal encoding."""
        from backend.services.cat.preprocessing import TemporalEncoder
        
        encoder = TemporalEncoder(encoding_dim=32)
        
        prediction_time = datetime(2026, 5, 15, 10, 0, 0)
        encoding = encoder.generate_temporal_encoding(prediction_time)
        
        assert len(encoding) == 32


class TestModel:
    """Tests for CAT model."""
    
    def test_model_initialization(self):
        """Test model initialization."""
        from backend.services.cat.model import CATModel, ModelConfig
        
        config = ModelConfig()
        model = CATModel(config)
        
        assert model is not None
        assert model.config == config
    
    def test_model_forward_pass(self):
        """Test model forward pass."""
        from backend.services.cat.model import CATModel, ModelConfig
        from backend.services.cat.data_models import ModelInput
        
        config = ModelConfig()
        model = CATModel(config)
        
        # Create model input
        model_input = ModelInput(
            event_embeddings=[0.0] * 128,
            weather_embeddings=[0.0] * 64,
            historical_sequence=[0.0] * 120,  # 24 * 5
            temporal_encoding=[0.0] * 32,
        )
        
        # Run forward pass
        prediction = model(model_input)
        
        assert prediction.probability >= 0.0
        assert prediction.probability <= 1.0
        assert len(prediction.contributing_factors) > 0
    
    def test_multi_head_attention(self):
        """Test multi-head attention mechanism."""
        from backend.services.cat.model import MultiHeadAttention
        
        model_dim = 256
        num_heads = 8
        attention = MultiHeadAttention(model_dim, num_heads)
        
        batch_size = 2
        seq_len = 10
        
        query = torch.randn(batch_size, seq_len, model_dim)
        key = torch.randn(batch_size, seq_len, model_dim)
        value = torch.randn(batch_size, seq_len, model_dim)
        
        output, attention_weights = attention(query, key, value)
        
        assert output.shape == (batch_size, seq_len, model_dim)
        assert attention_weights.shape == (batch_size, num_heads, seq_len, seq_len)


class TestIntegration:
    """Integration tests for CAT components."""
    
    def test_end_to_end_preprocessing(self):
        """Test end-to-end preprocessing pipeline."""
        from backend.services.cat.preprocessing import PreprocessingModule
        from backend.services.cat.data_models import (
            ContextualData,
            EventCalendarData,
            WeatherData,
            HistoricalAvailabilityData,
        )
        
        module = PreprocessingModule()
        
        # Create sample contextual data
        contextual_data = ContextualData(
            event_calendar=EventCalendarData(events=[]),
            weather=WeatherData(current_conditions=WeatherConditions(
                temperature=25.0,
                humidity=60.0,
                precipitation_probability=0.1,
                wind_speed=10.0,
                weather_type=WeatherType.CLEAR,
            )),
            historical_availability=HistoricalAvailabilityData(
                records=[],
                location_id="NDLS",
            ),
        )
        
        # Preprocess
        model_input = module.preprocess_contextual_data(contextual_data)
        
        assert model_input.event_embeddings is not None
        assert model_input.weather_embeddings is not None
        assert model_input.historical_sequence is not None
        assert model_input.temporal_encoding is not None
    
    def test_model_with_preprocessed_input(self):
        """Test model with preprocessed input."""
        from backend.services.cat.preprocessing import PreprocessingModule
        from backend.services.cat.model import CATModel, ModelConfig
        from backend.services.cat.data_models import ContextualData
        
        config = ModelConfig()
        model = CATModel(config)
        module = PreprocessingModule()
        
        # Create sample contextual data
        contextual_data = ContextualData(
            event_calendar=EventCalendarData(events=[]),
            weather=WeatherData(current_conditions=WeatherConditions(
                temperature=25.0,
                humidity=60.0,
                precipitation_probability=0.1,
                wind_speed=10.0,
                weather_type=WeatherType.CLEAR,
            )),
            historical_availability=HistoricalAvailabilityData(
                records=[],
                location_id="NDLS",
            ),
        )
        
        # Preprocess
        model_input = module.preprocess_contextual_data(contextual_data)
        
        # Validate input
        assert module.validate_model_input(model_input)
        
        # Run prediction
        prediction = model(model_input)
        
        assert prediction.probability >= 0.0
        assert prediction.probability <= 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])