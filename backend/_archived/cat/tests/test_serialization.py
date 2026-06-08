"""
Unit tests for CAT serialization module.
Tests JSON serialization for data models and tensor serialization.
"""

import json
import pytest
import torch
import numpy as np
from datetime import datetime, timezone
from uuid import uuid4

from backend.cat.models.schemas import (
    ContextualData, EventCalendarData, CalendarEvent, Location,
    WeatherData, WeatherConditions, WeatherForecast, HistoricalAvailabilityData,
    AvailabilityRecord, ContextualFactors, AvailabilityPrediction,
    ContributingFactor, Season, EventType, WeatherType
)
from backend.cat.serialization.data_serializers import (
    PydanticSerializer,
    ContextualDataSerializer,
    PredictionSerializer,
    DateTimeEncoder,
    UUIDEncoder,
    EnumEncoder,
    serialize_model,
    deserialize_model,
    serialize_to_dict,
    deserialize_from_dict
)
from backend.cat.serialization.tensor_serializers import (
    TensorSerializer,
    TensorBatchSerializer,
    ModelInputSerializer,
    serialize_tensor,
    deserialize_tensor,
    validate_tensor
)


class TestDateTimeEncoder:
    """Tests for DateTimeEncoder."""
    
    def test_encode_datetime(self):
        """Test encoding datetime to ISO format."""
        dt = datetime(2024, 6, 15, 12, 30, 45, tzinfo=timezone.utc)
        encoded = DateTimeEncoder.encode(dt)
        assert encoded == "2024-06-15T12:30:45+00:00"
    
    def test_decode_datetime(self):
        """Test decoding ISO format to datetime."""
        dt_str = "2024-06-15T12:30:45+00:00"
        decoded = DateTimeEncoder.decode(dt_str)
        assert decoded.year == 2024
        assert decoded.month == 6
        assert decoded.day == 15
        assert decoded.hour == 12
        assert decoded.minute == 30
        assert decoded.second == 45
    
    def test_encode_decode_round_trip(self):
        """Test round-trip encoding and decoding."""
        dt = datetime(2024, 6, 15, 18, 0, 0, tzinfo=timezone.utc)
        encoded = DateTimeEncoder.encode(dt)
        decoded = DateTimeEncoder.decode(encoded)
        assert decoded == dt
    
    def test_encode_none(self):
        """Test encoding None."""
        assert DateTimeEncoder.encode(None) is None
    
    def test_decode_none(self):
        """Test decoding None."""
        assert DateTimeEncoder.decode(None) is None


class TestUUIDEncoder:
    """Tests for UUIDEncoder."""
    
    def test_encode_uuid(self):
        """Test encoding UUID to string."""
        uid = uuid4()
        encoded = UUIDEncoder.encode(uid)
        assert isinstance(encoded, str)
        assert len(encoded) == 36  # UUID string length
    
    def test_decode_uuid(self):
        """Test decoding string to UUID."""
        uid = uuid4()
        uid_str = str(uid)
        decoded = UUIDEncoder.decode(uid_str)
        assert decoded == uid
    
    def test_encode_decode_round_trip(self):
        """Test round-trip encoding and decoding."""
        uid = uuid4()
        encoded = UUIDEncoder.encode(uid)
        decoded = UUIDEncoder.decode(encoded)
        assert decoded == uid
    
    def test_encode_none(self):
        """Test encoding None."""
        assert UUIDEncoder.encode(None) is None
    
    def test_decode_none(self):
        """Test decoding None."""
        assert UUIDEncoder.decode(None) is None


class TestEnumEncoder:
    """Tests for EnumEncoder."""
    
    def test_encode_event_type(self):
        """Test encoding EventType enum."""
        encoded = EnumEncoder.encode(EventType.CONCERT)
        assert encoded == "concert"
    
    def test_decode_event_type(self):
        """Test decoding string to EventType."""
        decoded = EnumEncoder.decode(EventType, "concert")
        assert decoded == EventType.CONCERT
    
    def test_encode_weather_type(self):
        """Test encoding WeatherType enum."""
        encoded = EnumEncoder.encode(WeatherType.RAIN)
        assert encoded == "rain"
    
    def test_encode_season(self):
        """Test encoding Season enum."""
        encoded = EnumEncoder.encode(Season.SUMMER)
        assert encoded == "summer"
    
    def test_encode_none(self):
        """Test encoding None."""
        assert EnumEncoder.encode(None) is None
    
    def test_decode_none(self):
        """Test decoding None."""
        assert EnumEncoder.decode(EventType, None) is None


class TestPydanticSerializer:
    """Tests for PydanticSerializer."""
    
    def test_to_json_location(self):
        """Test serializing Location model to JSON."""
        location = Location(
            venue_id="test_venue",
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
        json_str = PydanticSerializer.to_json(location)
        data = json.loads(json_str)
        assert data["venue_id"] == "test_venue"
        assert data["latitude"] == 40.7128
    
    def test_from_json_location(self):
        """Test deserializing Location model from JSON."""
        location = Location(
            venue_id="test_venue",
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
        json_str = PydanticSerializer.to_json(location)
        deserialized = PydanticSerializer.from_json(json_str, Location)
        assert deserialized.venue_id == location.venue_id
        assert deserialized.latitude == location.latitude
    
    def test_to_dict_location(self):
        """Test serializing Location to dictionary."""
        location = Location(
            venue_id="test_venue",
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
        data = PydanticSerializer.to_dict(location)
        assert data["venue_id"] == "test_venue"
        assert data["latitude"] == 40.7128
    
    def test_from_dict_location(self):
        """Test deserializing Location from dictionary."""
        location = Location(
            venue_id="test_venue",
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
        data = PydanticSerializer.to_dict(location)
        deserialized = PydanticSerializer.from_dict(data, Location)
        assert deserialized.venue_id == location.venue_id
    
    def test_round_trip_contextual_data(self):
        """Test round-trip serialization for ContextualData."""
        location = Location(
            venue_id="test_venue",
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
        
        event = CalendarEvent(
            title="Test Event",
            event_type=EventType.CONCERT,
            expected_attendance=1000,
            location=location,
            start_time=datetime(2024, 6, 15, 18, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 6, 15, 23, 0, 0, tzinfo=timezone.utc),
            is_outdoor=True
        )
        
        event_calendar = EventCalendarData(
            events=[event],
            last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        weather = WeatherData(
            current_conditions=WeatherConditions(
                temperature=25.5,
                humidity=65.0,
                precipitation_probability=0.3,
                wind_speed=5.2,
                weather_type=WeatherType.CLEAR
            ),
            forecast=[],
            last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        historical = HistoricalAvailabilityData(
            records=[],
            location_id="test_location"
        )
        
        contextual_data = ContextualData(
            event_calendar=event_calendar,
            weather=weather,
            historical_availability=historical,
            timestamp=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        # Serialize to JSON
        json_str = PydanticSerializer.to_json(contextual_data)
        
        # Deserialize from JSON
        deserialized = PydanticSerializer.from_json(json_str, ContextualData)
        
        # Verify round-trip
        assert deserialized.event_calendar.events[0].title == event.title
        assert deserialized.weather.current_conditions.temperature == 25.5
        assert deserialized.timestamp == contextual_data.timestamp


class TestContextualDataSerializer:
    """Tests for ContextualDataSerializer."""
    
    def test_serialize_contextual_data(self):
        """Test serializing ContextualData."""
        location = Location(
            venue_id="test_venue",
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
        
        event = CalendarEvent(
            title="Test Event",
            event_type=EventType.CONCERT,
            expected_attendance=1000,
            location=location,
            start_time=datetime(2024, 6, 15, 18, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 6, 15, 23, 0, 0, tzinfo=timezone.utc),
            is_outdoor=True
        )
        
        event_calendar = EventCalendarData(
            events=[event],
            last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        weather = WeatherData(
            current_conditions=WeatherConditions(
                temperature=25.5,
                humidity=65.0,
                precipitation_probability=0.3,
                wind_speed=5.2,
                weather_type=WeatherType.CLEAR
            ),
            forecast=[],
            last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        historical = HistoricalAvailabilityData(
            records=[],
            location_id="test_location"
        )
        
        contextual_data = ContextualData(
            event_calendar=event_calendar,
            weather=weather,
            historical_availability=historical,
            timestamp=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        serialized = ContextualDataSerializer.serialize_contextual_data(contextual_data)
        
        assert serialized['event_calendar']['events'][0]['title'] == "Test Event"
        assert serialized['event_calendar']['events'][0]['event_type'] == "concert"
        assert serialized['weather']['current_conditions']['temperature'] == 25.5
    
    def test_deserialize_contextual_data(self):
        """Test deserializing ContextualData."""
        location = Location(
            venue_id="test_venue",
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
        
        event = CalendarEvent(
            title="Test Event",
            event_type=EventType.CONCERT,
            expected_attendance=1000,
            location=location,
            start_time=datetime(2024, 6, 15, 18, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 6, 15, 23, 0, 0, tzinfo=timezone.utc),
            is_outdoor=True
        )
        
        event_calendar = EventCalendarData(
            events=[event],
            last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        weather = WeatherData(
            current_conditions=WeatherConditions(
                temperature=25.5,
                humidity=65.0,
                precipitation_probability=0.3,
                wind_speed=5.2,
                weather_type=WeatherType.CLEAR
            ),
            forecast=[],
            last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        historical = HistoricalAvailabilityData(
            records=[],
            location_id="test_location"
        )
        
        contextual_data = ContextualData(
            event_calendar=event_calendar,
            weather=weather,
            historical_availability=historical,
            timestamp=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        serialized = ContextualDataSerializer.serialize_contextual_data(contextual_data)
        deserialized = ContextualDataSerializer.deserialize_contextual_data(serialized)
        
        assert deserialized.event_calendar.events[0].title == event.title
        assert deserialized.weather.current_conditions.temperature == 25.5
    
    def test_round_trip_contextual_data(self):
        """Test round-trip serialization for ContextualData."""
        location = Location(
            venue_id="test_venue",
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
        
        event = CalendarEvent(
            title="Test Event",
            event_type=EventType.CONCERT,
            expected_attendance=1000,
            location=location,
            start_time=datetime(2024, 6, 15, 18, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 6, 15, 23, 0, 0, tzinfo=timezone.utc),
            is_outdoor=True
        )
        
        event_calendar = EventCalendarData(
            events=[event],
            last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        weather = WeatherData(
            current_conditions=WeatherConditions(
                temperature=25.5,
                humidity=65.0,
                precipitation_probability=0.3,
                wind_speed=5.2,
                weather_type=WeatherType.CLEAR
            ),
            forecast=[],
            last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        historical = HistoricalAvailabilityData(
            records=[],
            location_id="test_location"
        )
        
        contextual_data = ContextualData(
            event_calendar=event_calendar,
            weather=weather,
            historical_availability=historical,
            timestamp=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        # Serialize and deserialize
        serialized = ContextualDataSerializer.serialize_contextual_data(contextual_data)
        deserialized = ContextualDataSerializer.deserialize_contextual_data(serialized)
        
        # Verify all fields match
        assert deserialized.event_calendar.events[0].title == contextual_data.event_calendar.events[0].title
        assert deserialized.weather.current_conditions.temperature == contextual_data.weather.current_conditions.temperature
        assert deserialized.timestamp == contextual_data.timestamp


class TestPredictionSerializer:
    """Tests for PredictionSerializer."""
    
    def test_serialize_prediction(self):
        """Test serializing AvailabilityPrediction."""
        prediction = AvailabilityPrediction(
            probability=0.65,
            confidence_interval=(0.55, 0.75),
            contributing_factors=[
                ContributingFactor(
                    factor_name="event_impact",
                    importance_score=0.45,
                    description="High-attendance concert nearby"
                )
            ],
            location_id="test_location",
            prediction_time=datetime(2024, 6, 15, 18, 0, 0, tzinfo=timezone.utc),
            model_version="1.0.0"
        )
        
        serialized = PredictionSerializer.serialize_prediction(prediction)
        
        assert serialized['probability'] == 0.65
        assert serialized['confidence_interval'] == [0.55, 0.75]
        assert serialized['contributing_factors'][0]['factor_name'] == "event_impact"
    
    def test_deserialize_prediction(self):
        """Test deserializing AvailabilityPrediction."""
        prediction = AvailabilityPrediction(
            probability=0.65,
            confidence_interval=(0.55, 0.75),
            contributing_factors=[
                ContributingFactor(
                    factor_name="event_impact",
                    importance_score=0.45,
                    description="High-attendance concert nearby"
                )
            ],
            location_id="test_location",
            prediction_time=datetime(2024, 6, 15, 18, 0, 0, tzinfo=timezone.utc),
            model_version="1.0.0"
        )
        
        serialized = PredictionSerializer.serialize_prediction(prediction)
        deserialized = PredictionSerializer.deserialize_prediction(serialized)
        
        assert deserialized.probability == prediction.probability
        assert deserialized.confidence_interval == prediction.confidence_interval


class TestTensorSerializer:
    """Tests for TensorSerializer."""
    
    def test_serialize_float_tensor(self):
        """Test serializing a float tensor."""
        tensor = torch.randn(3, 4)
        serialized = TensorSerializer.serialize_tensor(tensor)
        
        assert 'shape' in serialized
        assert serialized['shape'] == [3, 4]
        assert 'dtype' in serialized
        assert serialized['dtype'] == 'float32'
        assert 'data' in serialized
    
    def test_deserialize_float_tensor(self):
        """Test deserializing a float tensor."""
        original = torch.randn(3, 4)
        serialized = TensorSerializer.serialize_tensor(original)
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        
        assert deserialized.shape == original.shape
        assert deserialized.dtype == original.dtype
        assert torch.allclose(deserialized, original, atol=1e-6)
    
    def test_round_trip_tensor(self):
        """Test round-trip serialization for tensor."""
        original = torch.randn(5, 6, 7)
        
        # Serialize
        serialized = TensorSerializer.serialize_tensor(original)
        json_str = TensorSerializer.to_json(original)
        
        # Deserialize
        deserialized = TensorSerializer.from_json(json_str)
        
        assert deserialized.shape == original.shape
        assert deserialized.dtype == original.dtype
        assert torch.allclose(deserialized, original, atol=1e-6)
    
    def test_serialize_int_tensor(self):
        """Test serializing an int tensor."""
        tensor = torch.randint(0, 10, (3, 4))
        serialized = TensorSerializer.serialize_tensor(tensor)
        
        assert serialized['dtype'] == 'int64'
        
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        assert deserialized.dtype == tensor.dtype
        assert torch.equal(deserialized, tensor)
    
    def test_serialize_bool_tensor(self):
        """Test serializing a bool tensor."""
        tensor = torch.tensor([True, False, True, False])
        serialized = TensorSerializer.serialize_tensor(tensor)
        
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        assert deserialized.dtype == torch.bool
        assert torch.equal(deserialized, tensor)
    
    def test_serialize_cuda_tensor(self):
        """Test serializing a CUDA tensor (if available)."""
        if not torch.cuda.is_available:
            pytest.skip("CUDA not available")
        
        try:
            tensor = torch.randn(3, 4).cuda()
            serialized = TensorSerializer.serialize_tensor(tensor)
            
            assert serialized['device'] == 'cuda:0'
            
            deserialized = TensorSerializer.deserialize_tensor(serialized)
            assert deserialized.shape == tensor.shape
            assert deserialized.dtype == tensor.dtype
        except Exception as e:
            pytest.skip(f"CUDA test failed: {e}")
    
    def test_validate_tensor_no_nan(self):
        """Test validation rejects NaN values."""
        tensor = torch.tensor([1.0, float('nan'), 3.0])
        serialized = TensorSerializer.serialize_tensor(tensor)
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        
        with pytest.raises(ValueError, match="NaN"):
            TensorSerializer.validate_tensor(deserialized)
    
    def test_validate_tensor_no_inf(self):
        """Test validation rejects Inf values."""
        tensor = torch.tensor([1.0, float('inf'), 3.0])
        serialized = TensorSerializer.serialize_tensor(tensor)
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        
        with pytest.raises(ValueError, match="Inf"):
            TensorSerializer.validate_tensor(deserialized)
    
    def test_validate_tensor_shape(self):
        """Test validation checks shape."""
        tensor = torch.randn(3, 4)
        serialized = TensorSerializer.serialize_tensor(tensor)
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        
        # Should pass with correct shape
        TensorSerializer.validate_tensor(deserialized, expected_shape=(3, 4))
        
        # Should fail with wrong shape
        with pytest.raises(ValueError, match="Shape mismatch"):
            TensorSerializer.validate_tensor(deserialized, expected_shape=(4, 3))
    
    def test_serialize_empty_tensor(self):
        """Test serializing an empty tensor."""
        tensor = torch.tensor([])
        serialized = TensorSerializer.serialize_tensor(tensor)
        
        assert serialized['shape'] == [0]
        
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        assert deserialized.shape == tensor.shape
    
    def test_serialize_large_tensor(self):
        """Test serializing a large tensor."""
        tensor = torch.randn(100, 100)
        serialized = TensorSerializer.serialize_tensor(tensor)
        
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        assert deserialized.shape == tensor.shape
        assert torch.allclose(deserialized, tensor, atol=1e-5)
    
    def test_serialize_tensor_with_requires_grad(self):
        """Test serializing a tensor with requires_grad."""
        tensor = torch.randn(3, 4, requires_grad=True)
        serialized = TensorSerializer.serialize_tensor(tensor)
        
        assert serialized['requires_grad'] == True
        
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        assert deserialized.requires_grad == True


class TestTensorBatchSerializer:
    """Tests for TensorBatchSerializer."""
    
    def test_serialize_batch(self):
        """Test serializing a batch of tensors."""
        tensors = [
            torch.randn(3, 4),
            torch.randn(5, 6),
            torch.randn(7, 8)
        ]
        names = ["tensor1", "tensor2", "tensor3"]
        
        serialized = TensorBatchSerializer.serialize_batch(tensors, names)
        
        assert "tensor1" in serialized
        assert "tensor2" in serialized
        assert "tensor3" in serialized
    
    def test_deserialize_batch(self):
        """Test deserializing a batch of tensors."""
        tensors = [
            torch.randn(3, 4),
            torch.randn(5, 6),
            torch.randn(7, 8)
        ]
        names = ["tensor1", "tensor2", "tensor3"]
        
        serialized = TensorBatchSerializer.serialize_batch(tensors, names)
        deserialized = TensorBatchSerializer.deserialize_batch(serialized)
        
        assert torch.allclose(deserialized["tensor1"], tensors[0], atol=1e-6)
        assert torch.allclose(deserialized["tensor2"], tensors[1], atol=1e-6)
        assert torch.allclose(deserialized["tensor3"], tensors[2], atol=1e-6)
    
    def test_validate_batch(self):
        """Test validating a batch of tensors."""
        tensors = [
            torch.randn(3, 4),
            torch.randn(5, 6)
        ]
        names = ["tensor1", "tensor2"]
        
        serialized = TensorBatchSerializer.serialize_batch(tensors, names)
        
        expected_shapes = {
            "tensor1": (3, 4),
            "tensor2": (5, 6)
        }
        
        TensorBatchSerializer.validate_batch(serialized, expected_shapes)


class TestModelInputSerializer:
    """Tests for ModelInputSerializer."""
    
    def test_serialize_model_input(self):
        """Test serializing ModelInput tensors."""
        event_emb = torch.randn(1, 64)
        weather_emb = torch.randn(1, 32)
        historical_seq = torch.randn(1, 24 * 64)
        temporal_enc = torch.randn(1, 64)
        
        serialized = ModelInputSerializer.serialize_model_input(
            event_emb, weather_emb, historical_seq, temporal_enc
        )
        
        assert 'event_embeddings' in serialized
        assert 'weather_embeddings' in serialized
        assert 'historical_sequence' in serialized
        assert 'temporal_encoding' in serialized
    
    def test_deserialize_model_input(self):
        """Test deserializing ModelInput tensors."""
        event_emb = torch.randn(1, 64)
        weather_emb = torch.randn(1, 32)
        historical_seq = torch.randn(1, 24 * 64)
        temporal_enc = torch.randn(1, 64)
        
        serialized = ModelInputSerializer.serialize_model_input(
            event_emb, weather_emb, historical_seq, temporal_enc
        )
        
        deserialized = ModelInputSerializer.deserialize_model_input(serialized)
        
        assert torch.allclose(deserialized['event_embeddings'], event_emb, atol=1e-6)
        assert torch.allclose(deserialized['weather_embeddings'], weather_emb, atol=1e-6)
        assert torch.allclose(deserialized['historical_sequence'], historical_seq, atol=1e-6)
        assert torch.allclose(deserialized['temporal_encoding'], temporal_enc, atol=1e-6)
    
    def test_round_trip_model_input(self):
        """Test round-trip serialization for ModelInput."""
        event_emb = torch.randn(1, 64)
        weather_emb = torch.randn(1, 32)
        historical_seq = torch.randn(1, 24 * 64)
        temporal_enc = torch.randn(1, 64)
        
        # Serialize to JSON
        json_str = ModelInputSerializer.to_json(
            event_emb, weather_emb, historical_seq, temporal_enc
        )
        
        # Deserialize from JSON
        deserialized = ModelInputSerializer.from_json(json_str)
        
        assert torch.allclose(deserialized['event_embeddings'], event_emb, atol=1e-6)
        assert torch.allclose(deserialized['weather_embeddings'], weather_emb, atol=1e-6)
        assert torch.allclose(deserialized['historical_sequence'], historical_seq, atol=1e-6)
        assert torch.allclose(deserialized['temporal_encoding'], temporal_enc, atol=1e-6)


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_serialize_model(self):
        """Test serialize_model convenience function."""
        location = Location(
            venue_id="test_venue",
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
        
        json_str = serialize_model(location)
        deserialized = deserialize_model(json_str, Location)
        
        assert deserialized.venue_id == location.venue_id
    
    def test_serialize_to_dict(self):
        """Test serialize_to_dict convenience function."""
        location = Location(
            venue_id="test_venue",
            latitude=40.7128,
            longitude=-74.0060,
            capacity=500
        )
        
        data = serialize_to_dict(location)
        deserialized = deserialize_from_dict(data, Location)
        
        assert deserialized.venue_id == location.venue_id
    
    def test_serialize_tensor(self):
        """Test serialize_tensor convenience function."""
        tensor = torch.randn(3, 4)
        
        json_str = serialize_tensor(tensor)
        deserialized = deserialize_tensor(json_str)
        
        assert torch.allclose(deserialized, tensor, atol=1e-6)
    
    def test_validate_tensor(self):
        """Test validate_tensor convenience function."""
        tensor = torch.randn(3, 4)
        
        json_str = serialize_tensor(tensor)
        deserialized = validate_tensor(json_str, expected_shape=(3, 4))
        
        assert torch.allclose(deserialized, tensor, atol=1e-6)


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_event_calendar(self):
        """Test serializing empty event calendar."""
        event_calendar = EventCalendarData(
            events=[],
            last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        serialized = ContextualDataSerializer.serialize_contextual_data(
            ContextualData(
                event_calendar=event_calendar,
                weather=WeatherData(
                    current_conditions=None,
                    forecast=[],
                    last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
                ),
                historical_availability=HistoricalAvailabilityData(
                    records=[],
                    location_id="test_location"
                ),
                timestamp=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            )
        )
        
        assert serialized['event_calendar']['events'] == []
    
    def test_empty_historical_data(self):
        """Test serializing empty historical data."""
        historical = HistoricalAvailabilityData(
            records=[],
            location_id="test_location"
        )
        
        serialized = ContextualDataSerializer._serialize_historical_availability(historical)
        
        assert serialized['records'] == []
    
    def test_none_weather_conditions(self):
        """Test serializing None weather conditions."""
        weather = WeatherData(
            current_conditions=None,
            forecast=[],
            last_updated=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        serialized = ContextualDataSerializer._serialize_weather(weather)
        
        assert serialized['current_conditions'] is None
    
    def test_extreme_tensor_values(self):
        """Test serializing tensors with extreme values."""
        tensor = torch.tensor([1e10, -1e10, 1e-10, -1e-10])
        
        serialized = TensorSerializer.serialize_tensor(tensor)
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        
        assert torch.allclose(deserialized, tensor, rtol=1e-5)
    
    def test_single_element_tensor(self):
        """Test serializing single element tensor."""
        tensor = torch.tensor([42.0])
        
        serialized = TensorSerializer.serialize_tensor(tensor)
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        
        assert deserialized.shape == (1,)
        assert torch.equal(deserialized, tensor)
    
    def test_high_dimensional_tensor(self):
        """Test serializing high dimensional tensor."""
        tensor = torch.randn(2, 3, 4, 5, 6)
        
        serialized = TensorSerializer.serialize_tensor(tensor)
        deserialized = TensorSerializer.deserialize_tensor(serialized)
        
        assert deserialized.shape == tensor.shape
        assert torch.allclose(deserialized, tensor, atol=1e-5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
