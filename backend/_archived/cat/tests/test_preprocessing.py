"""
Unit tests for the CAT preprocessing module.
Tests encoders, tensor operations, and data transformations.

Validates Requirements:
- 4.1: One-hot encoding for EventType enum
- 4.2: Normalized numerical encoding for event size
- 4.3: Location encoding using latitude/longitude
- 4.4: Temporal position encoding for event timing
- 4.5: Weather encoding (temperature, humidity, precipitation, wind, type)
- 4.6: Historical sequence encoding with contextual factors
- 4.7: Temporal encodings for sequence positions
- 4.8: Mean pooling for multiple events
- 4.9: Missing data handling with zero embeddings and validation
"""

import pytest
import torch
import numpy as np
from datetime import datetime, timedelta
from uuid import uuid4

from backend.cat.preprocessing.encoders import (
    EventEncoder,
    WeatherEncoder,
    HistoricalEncoder,
    TemporalEncoder,
    TensorPreprocessor,
    ModelInput,
)
from backend.cat.models.schemas import (
    EventCalendarData,
    WeatherData,
    HistoricalAvailabilityData,
    CalendarEvent,
    WeatherConditions,
    AvailabilityRecord,
    ContextualFactors,
    EventType,
    WeatherType,
    Season,
    Location,
)
from backend.cat.config import settings


class TestEventEncoder:
    """Tests for EventEncoder module - Requirements 4.1, 4.2, 4.3, 4.4, 4.8."""

    def test_empty_events(self):
        """Test encoding with no events - Requirement 4.9 (zero embedding)."""
        encoder = EventEncoder()

        event_data = EventCalendarData(events=[], last_updated=datetime.utcnow())

        embedding = encoder(event_data)

        assert embedding.shape[0] == settings.event_embedding_dim
        assert torch.all(embedding == 0)

    def test_single_event(self):
        """Test encoding with a single event."""
        encoder = EventEncoder()

        event = CalendarEvent(
            event_id=uuid4(),
            title="Test Concert",
            event_type=EventType.CONCERT,
            expected_attendance=500,
            location=Location(
                venue_id="test_venue",
                latitude=40.7128,
                longitude=-74.0060,
                capacity=1000,
            ),
            start_time=datetime(2024, 6, 15, 18, 0, 0),
            end_time=datetime(2024, 6, 15, 23, 0, 0),
            is_outdoor=True,
        )

        event_data = EventCalendarData(events=[event], last_updated=datetime.utcnow())

        embedding = encoder(event_data)

        assert embedding.shape[0] == settings.event_embedding_dim
        assert not torch.isnan(embedding).any()
        assert not torch.isinf(embedding).any()

    def test_multiple_events_mean_pooling(self):
        """Test encoding with multiple events (mean pooling) - Requirement 4.8."""
        encoder = EventEncoder()

        events = [
            CalendarEvent(
                event_id=uuid4(),
                title=f"Event {i}",
                event_type=EventType.CONCERT if i % 2 == 0 else EventType.SPORTS,
                expected_attendance=500 + i * 100,
                location=Location(
                    venue_id="test_venue",
                    latitude=40.7128,
                    longitude=-74.0060,
                    capacity=1000,
                ),
                start_time=datetime(2024, 6, 15, 18 + i, 0, 0),
                end_time=datetime(2024, 6, 15, 21 + i, 0, 0),
                is_outdoor=i % 2 == 0,
            )
            for i in range(3)
        ]

        event_data = EventCalendarData(events=events, last_updated=datetime.utcnow())

        embedding = encoder(event_data)

        assert embedding.shape[0] == settings.event_embedding_dim
        assert not torch.isnan(embedding).any()

    def test_all_event_types_one_hot(self):
        """Test encoding with all event types - Requirement 4.1 (one-hot encoding)."""
        encoder = EventEncoder()

        for event_type in EventType:
            event = CalendarEvent(
                event_id=uuid4(),
                title="Test Event",
                event_type=event_type,
                expected_attendance=500,
                location=Location(
                    venue_id="test_venue",
                    latitude=40.7128,
                    longitude=-74.0060,
                    capacity=1000,
                ),
                start_time=datetime(2024, 6, 15, 18, 0, 0),
                end_time=datetime(2024, 6, 15, 23, 0, 0),
                is_outdoor=False,
            )

            event_data = EventCalendarData(events=[event], last_updated=datetime.utcnow())
            embedding = encoder(event_data)

            assert embedding.shape[0] == settings.event_embedding_dim

    def test_event_size_normalization(self):
        """Test event size normalization - Requirement 4.2."""
        encoder = EventEncoder(max_attendance=10000)

        # Small event
        small_event = CalendarEvent(
            event_id=uuid4(),
            title="Small Event",
            event_type=EventType.OTHER,
            expected_attendance=100,
            location=Location(
                venue_id="test_venue",
                latitude=40.7128,
                longitude=-74.0060,
                capacity=1000,
            ),
            start_time=datetime(2024, 6, 15, 18, 0, 0),
            end_time=datetime(2024, 6, 15, 23, 0, 0),
            is_outdoor=False,
        )

        # Large event
        large_event = CalendarEvent(
            event_id=uuid4(),
            title="Large Event",
            event_type=EventType.OTHER,
            expected_attendance=10000,
            location=Location(
                venue_id="test_venue",
                latitude=40.7128,
                longitude=-74.0060,
                capacity=20000,
            ),
            start_time=datetime(2024, 6, 15, 18, 0, 0),
            end_time=datetime(2024, 6, 15, 23, 0, 0),
            is_outdoor=False,
        )

        small_embedding = encoder(EventCalendarData(events=[small_event], last_updated=datetime.utcnow()))
        large_embedding = encoder(EventCalendarData(events=[large_event], last_updated=datetime.utcnow()))

        # Large event should have different embedding than small event
        assert not torch.allclose(small_embedding, large_embedding)

    def test_location_encoding(self):
        """Test location encoding - Requirement 4.3."""
        encoder = EventEncoder()

        # Different locations
        event1 = CalendarEvent(
            event_id=uuid4(),
            title="Event 1",
            event_type=EventType.CONCERT,
            expected_attendance=500,
            location=Location(
                venue_id="venue_1",
                latitude=40.7128,
                longitude=-74.0060,
                capacity=1000,
            ),
            start_time=datetime(2024, 6, 15, 18, 0, 0),
            end_time=datetime(2024, 6, 15, 23, 0, 0),
            is_outdoor=False,
        )

        event2 = CalendarEvent(
            event_id=uuid4(),
            title="Event 2",
            event_type=EventType.CONCERT,
            expected_attendance=500,
            location=Location(
                venue_id="venue_2",
                latitude=51.5074,  # London
                longitude=-0.1278,
                capacity=1000,
            ),
            start_time=datetime(2024, 6, 15, 18, 0, 0),
            end_time=datetime(2024, 6, 15, 23, 0, 0),
            is_outdoor=False,
        )

        embedding1 = encoder(EventCalendarData(events=[event1], last_updated=datetime.utcnow()))
        embedding2 = encoder(EventCalendarData(events=[event2], last_updated=datetime.utcnow()))

        # Different locations should produce different embeddings
        assert not torch.allclose(embedding1, embedding2)

    def test_temporal_encoding(self):
        """Test temporal position encoding - Requirement 4.4."""
        encoder = EventEncoder()

        # Different times
        event1 = CalendarEvent(
            event_id=uuid4(),
            title="Morning Event",
            event_type=EventType.CONFERENCE,
            expected_attendance=500,
            location=Location(
                venue_id="test_venue",
                latitude=40.7128,
                longitude=-74.0060,
                capacity=1000,
            ),
            start_time=datetime(2024, 6, 15, 9, 0, 0),
            end_time=datetime(2024, 6, 15, 17, 0, 0),
            is_outdoor=False,
        )

        event2 = CalendarEvent(
            event_id=uuid4(),
            title="Evening Event",
            event_type=EventType.CONFERENCE,
            expected_attendance=500,
            location=Location(
                venue_id="test_venue",
                latitude=40.7128,
                longitude=-74.0060,
                capacity=1000,
            ),
            start_time=datetime(2024, 6, 15, 18, 0, 0),
            end_time=datetime(2024, 6, 15, 23, 0, 0),
            is_outdoor=False,
        )

        embedding1 = encoder(EventCalendarData(events=[event1], last_updated=datetime.utcnow()))
        embedding2 = encoder(EventCalendarData(events=[event2], last_updated=datetime.utcnow()))

        # Different times should produce different embeddings
        assert not torch.allclose(embedding1, embedding2)


class TestWeatherEncoder:
    """Tests for WeatherEncoder module - Requirement 4.5."""

    def test_empty_weather(self):
        """Test encoding with no weather data - Requirement 4.9 (zero embedding)."""
        encoder = WeatherEncoder()

        weather_data = WeatherData(
            current_conditions=None,
            forecast=[],
            last_updated=datetime.utcnow(),
        )

        embedding = encoder(weather_data)

        assert embedding.shape[0] == settings.weather_embedding_dim
        assert torch.all(embedding == 0)

    def test_current_conditions(self):
        """Test encoding with current conditions."""
        encoder = WeatherEncoder()

        conditions = WeatherConditions(
            temperature=25.5,
            humidity=65.0,
            precipitation_probability=0.3,
            wind_speed=5.2,
            weather_type=WeatherType.CLEAR,
        )

        weather_data = WeatherData(
            current_conditions=conditions,
            forecast=[],
            last_updated=datetime.utcnow(),
        )

        embedding = encoder(weather_data)

        assert embedding.shape[0] == settings.weather_embedding_dim
        assert not torch.isnan(embedding).any()
        assert not torch.isinf(embedding).any()

    def test_all_weather_types(self):
        """Test encoding with all weather types - Requirement 4.5 (one-hot type)."""
        encoder = WeatherEncoder()

        for weather_type in WeatherType:
            conditions = WeatherConditions(
                temperature=20.0,
                humidity=50.0,
                precipitation_probability=0.5,
                wind_speed=3.0,
                weather_type=weather_type,
            )

            weather_data = WeatherData(
                current_conditions=conditions,
                forecast=[],
                last_updated=datetime.utcnow(),
            )

            embedding = encoder(weather_data)

            assert embedding.shape[0] == settings.weather_embedding_dim

    def test_weather_value_ranges(self):
        """Test encoding with various weather values - Requirement 4.5."""
        encoder = WeatherEncoder()

        test_cases = [
            {"temperature": -10.0, "humidity": 0.0, "precipitation": 0.0, "wind": 0.0},
            {"temperature": 60.0, "humidity": 100.0, "precipitation": 1.0, "wind": 50.0},
            {"temperature": 0.0, "humidity": 50.0, "precipitation": 0.5, "wind": 10.0},
        ]

        for case in test_cases:
            conditions = WeatherConditions(
                temperature=case["temperature"],
                humidity=case["humidity"],
                precipitation_probability=case["precipitation"],
                wind_speed=case["wind"],
                weather_type=WeatherType.CLEAR,
            )

            weather_data = WeatherData(
                current_conditions=conditions,
                forecast=[],
                last_updated=datetime.utcnow(),
            )

            embedding = encoder(weather_data)

            assert not torch.isnan(embedding).any()
            assert not torch.isinf(embedding).any()

    def test_temperature_normalization(self):
        """Test temperature normalization - Requirement 4.5."""
        encoder = WeatherEncoder()

        cold = WeatherConditions(
            temperature=-30.0,
            humidity=50.0,
            precipitation_probability=0.0,
            wind_speed=5.0,
            weather_type=WeatherType.CLEAR,
        )

        hot = WeatherConditions(
            temperature=50.0,
            humidity=50.0,
            precipitation_probability=0.0,
            wind_speed=5.0,
            weather_type=WeatherType.CLEAR,
        )

        cold_emb = encoder(WeatherData(current_conditions=cold, forecast=[], last_updated=datetime.utcnow()))
        hot_emb = encoder(WeatherData(current_conditions=hot, forecast=[], last_updated=datetime.utcnow()))

        # Different temperatures should produce different embeddings
        assert not torch.allclose(cold_emb, hot_emb)

    def test_wind_speed_encoding(self):
        """Test wind speed encoding - Requirement 4.5."""
        encoder = WeatherEncoder()

        calm = WeatherConditions(
            temperature=25.0,
            humidity=50.0,
            precipitation_probability=0.0,
            wind_speed=0.0,
            weather_type=WeatherType.CLEAR,
        )

        windy = WeatherConditions(
            temperature=25.0,
            humidity=50.0,
            precipitation_probability=0.0,
            wind_speed=40.0,
            weather_type=WeatherType.WINDY,
        )

        calm_emb = encoder(WeatherData(current_conditions=calm, forecast=[], last_updated=datetime.utcnow()))
        windy_emb = encoder(WeatherData(current_conditions=windy, forecast=[], last_updated=datetime.utcnow()))

        # Different wind speeds should produce different embeddings
        assert not torch.allclose(calm_emb, windy_emb)


class TestHistoricalEncoder:
    """Tests for HistoricalEncoder module - Requirements 4.6, 4.7."""

    def test_empty_history(self):
        """Test encoding with no historical data - Requirement 4.9 (zero embedding)."""
        encoder = HistoricalEncoder()

        historical_data = HistoricalAvailabilityData(
            records=[],
            location_id="test_location",
        )

        sequence = encoder(historical_data)

        assert sequence.shape[0] == settings.historical_sequence_length
        assert sequence.shape[1] == settings.event_embedding_dim
        assert torch.all(sequence == 0)

    def test_single_record(self):
        """Test encoding with a single historical record."""
        encoder = HistoricalEncoder()

        record = AvailabilityRecord(
            timestamp=datetime(2024, 6, 15, 18, 0, 0),
            available_slots=150,
            total_slots=500,
            utilization_rate=0.7,
            contextual_factors=ContextualFactors(
                event_count=2,
                weather_severity=3,
                is_holiday=False,
                is_weekend=True,
                season=Season.SUMMER,
            ),
        )

        historical_data = HistoricalAvailabilityData(
            records=[record],
            location_id="test_location",
        )

        sequence = encoder(historical_data)

        assert sequence.shape[0] == settings.historical_sequence_length
        assert sequence.shape[1] == settings.event_embedding_dim
        assert not torch.isnan(sequence).any()

    def test_multiple_records(self):
        """Test encoding with multiple historical records."""
        encoder = HistoricalEncoder()

        records = [
            AvailabilityRecord(
                timestamp=datetime(2024, 6, 15, 17, 0, 0) - timedelta(hours=i),
                available_slots=150 + i * 10,
                total_slots=500,
                utilization_rate=0.7 - i * 0.02,
                contextual_factors=ContextualFactors(
                    event_count=i,
                    weather_severity=i % 5,
                    is_holiday=False,
                    is_weekend=i % 7 >= 5,
                    season=Season.SUMMER,
                ),
            )
            for i in range(10)
        ]

        historical_data = HistoricalAvailabilityData(
            records=records,
            location_id="test_location",
        )

        sequence = encoder(historical_data)

        assert sequence.shape[0] == settings.historical_sequence_length
        assert not torch.isnan(sequence).any()

    def test_sequence_length_limit(self):
        """Test that sequence length is limited to max_length - Requirement 4.6."""
        encoder = HistoricalEncoder(max_sequence_length=24)

        # Create more records than max_length
        records = [
            AvailabilityRecord(
                timestamp=datetime(2024, 6, 15, 18, 0, 0) - timedelta(hours=i),
                available_slots=150,
                total_slots=500,
                utilization_rate=0.7,
                contextual_factors=ContextualFactors(),
            )
            for i in range(50)
        ]

        historical_data = HistoricalAvailabilityData(
            records=records,
            location_id="test_location",
        )

        sequence = encoder(historical_data)

        # Should be limited to max_length
        assert sequence.shape[0] == 24

    def test_contextual_factors_encoding(self):
        """Test contextual factors encoding - Requirement 4.6."""
        encoder = HistoricalEncoder()

        # Weekend with events
        record1 = AvailabilityRecord(
            timestamp=datetime(2024, 6, 15, 18, 0, 0),
            available_slots=100,
            total_slots=500,
            utilization_rate=0.8,
            contextual_factors=ContextualFactors(
                event_count=5,
                weather_severity=5,
                is_holiday=True,
                is_weekend=True,
                season=Season.SUMMER,
            ),
        )

        # Weekday without events
        record2 = AvailabilityRecord(
            timestamp=datetime(2024, 6, 15, 18, 0, 0),
            available_slots=400,
            total_slots=500,
            utilization_rate=0.2,
            contextual_factors=ContextualFactors(
                event_count=0,
                weather_severity=0,
                is_holiday=False,
                is_weekend=False,
                season=Season.WINTER,
            ),
        )

        seq1 = encoder(HistoricalAvailabilityData(records=[record1], location_id="test"))
        seq2 = encoder(HistoricalAvailabilityData(records=[record2], location_id="test"))

        # Different contextual factors should produce different embeddings
        assert not torch.allclose(seq1[0], seq2[0])

    def test_variable_length_padding(self):
        """Test variable-length sequence handling with padding - Requirement 4.6."""
        encoder = HistoricalEncoder(max_sequence_length=24)

        # Create fewer records than max_length
        records = [
            AvailabilityRecord(
                timestamp=datetime(2024, 6, 15, 18, 0, 0) - timedelta(hours=i),
                available_slots=150,
                total_slots=500,
                utilization_rate=0.7,
                contextual_factors=ContextualFactors(),
            )
            for i in range(5)
        ]

        historical_data = HistoricalAvailabilityData(
            records=records,
            location_id="test_location",
        )

        sequence = encoder(historical_data)

        # Should be padded to max_length
        assert sequence.shape[0] == 24
        # First 5 should have data, rest should be zeros
        assert not torch.all(sequence[0] == 0)
        assert torch.all(sequence[-1] == 0)


class TestTemporalEncoder:
    """Tests for TemporalEncoder module - Requirement 4.7."""

    def test_single_timestamp(self):
        """Test encoding a single timestamp."""
        encoder = TemporalEncoder()

        timestamp = datetime(2024, 6, 15, 18, 30, 0)

        encoding = encoder(timestamp)

        assert encoding.shape[0] == settings.temporal_encoding_dim
        assert not torch.isnan(encoding).any()

    def test_different_times(self):
        """Test encoding different times of day."""
        encoder = TemporalEncoder()

        times = [
            datetime(2024, 6, 15, 0, 0, 0),
            datetime(2024, 6, 15, 6, 0, 0),
            datetime(2024, 6, 15, 12, 0, 0),
            datetime(2024, 6, 15, 18, 0, 0),
            datetime(2024, 6, 15, 23, 59, 59),
        ]

        encodings = [encoder(t) for t in times]

        # All encodings should have the same shape
        for enc in encodings:
            assert enc.shape[0] == settings.temporal_encoding_dim

        # Different times should produce different encodings
        for i in range(len(encodings)):
            for j in range(i + 1, len(encodings)):
                assert not torch.allclose(encodings[i], encodings[j])

    def test_encode_range(self):
        """Test encoding a range of timestamps - Requirement 4.7."""
        encoder = TemporalEncoder()

        start_time = datetime(2024, 6, 15, 0, 0, 0)
        end_time = datetime(2024, 6, 15, 23, 0, 0)
        num_steps = 24

        encodings = encoder.encode_range(start_time, end_time, num_steps)

        assert encodings.shape[0] == num_steps
        assert encodings.shape[1] == settings.temporal_encoding_dim

    def test_temporal_encoding_properties(self):
        """Test that temporal encoding has expected properties."""
        encoder = TemporalEncoder(embedding_dim=64, max_time_steps=1000)

        # Same time should produce same encoding
        t1 = datetime(2024, 6, 15, 12, 0, 0)
        t2 = datetime(2024, 6, 15, 12, 0, 0)
        assert torch.allclose(encoder(t1), encoder(t2))

        # Different times should produce different encodings
        t3 = datetime(2024, 6, 15, 18, 0, 0)
        assert not torch.allclose(encoder(t1), encoder(t3))


class TestModelInput:
    """Tests for ModelInput dataclass - Requirement 4.9."""

    def test_model_input_creation(self):
        """Test creating ModelInput from tensors."""
        event_emb = torch.randn(settings.event_embedding_dim)
        weather_emb = torch.randn(settings.weather_embedding_dim)
        hist_seq = torch.randn(settings.historical_sequence_length, settings.event_embedding_dim)
        temp_enc = torch.randn(settings.temporal_encoding_dim)

        model_input = ModelInput(
            event_embeddings=event_emb,
            weather_embeddings=weather_emb,
            historical_sequence=hist_seq,
            temporal_encoding=temp_enc,
        )

        assert model_input.event_embeddings.shape == torch.Size([settings.event_embedding_dim])
        assert model_input.weather_embeddings.shape == torch.Size([settings.weather_embedding_dim])
        assert model_input.historical_sequence.shape == torch.Size(
            [settings.historical_sequence_length, settings.event_embedding_dim]
        )
        assert model_input.temporal_encoding.shape == torch.Size([settings.temporal_encoding_dim])

    def test_model_input_validation(self):
        """Test ModelInput validation - Requirement 4.9."""
        event_emb = torch.randn(settings.event_embedding_dim)
        weather_emb = torch.randn(settings.weather_embedding_dim)
        hist_seq = torch.randn(settings.historical_sequence_length, settings.event_embedding_dim)
        temp_enc = torch.randn(settings.temporal_encoding_dim)

        model_input = ModelInput(
            event_embeddings=event_emb,
            weather_embeddings=weather_emb,
            historical_sequence=hist_seq,
            temporal_encoding=temp_enc,
        )

        assert model_input.validate() is True

    def test_model_input_validation_nan(self):
        """Test ModelInput validation with NaN - Requirement 4.9."""
        event_emb = torch.randn(settings.event_embedding_dim)
        event_emb[0] = float("nan")

        model_input = ModelInput(
            event_embeddings=event_emb,
            weather_embeddings=torch.randn(settings.weather_embedding_dim),
            historical_sequence=torch.randn(settings.historical_sequence_length, settings.event_embedding_dim),
            temporal_encoding=torch.randn(settings.temporal_encoding_dim),
        )

        with pytest.raises(ValueError, match="NaN detected"):
            model_input.validate()

    def test_model_input_validation_inf(self):
        """Test ModelInput validation with Inf - Requirement 4.9."""
        event_emb = torch.randn(settings.event_embedding_dim)
        event_emb[0] = float("inf")

        model_input = ModelInput(
            event_embeddings=event_emb,
            weather_embeddings=torch.randn(settings.weather_embedding_dim),
            historical_sequence=torch.randn(settings.historical_sequence_length, settings.event_embedding_dim),
            temporal_encoding=torch.randn(settings.temporal_encoding_dim),
        )

        with pytest.raises(ValueError, match="Inf detected"):
            model_input.validate()

    def test_model_input_validation_wrong_shape(self):
        """Test ModelInput validation with wrong shape - Requirement 4.9."""
        event_emb = torch.randn(settings.event_embedding_dim + 10)

        model_input = ModelInput(
            event_embeddings=event_emb,
            weather_embeddings=torch.randn(settings.weather_embedding_dim),
            historical_sequence=torch.randn(settings.historical_sequence_length, settings.event_embedding_dim),
            temporal_encoding=torch.randn(settings.temporal_encoding_dim),
        )

        with pytest.raises(ValueError, match="dimension mismatch"):
            model_input.validate()

    def test_model_input_to_device(self):
        """Test ModelInput device movement."""
        event_emb = torch.randn(settings.event_embedding_dim)
        weather_emb = torch.randn(settings.weather_embedding_dim)
        hist_seq = torch.randn(settings.historical_sequence_length, settings.event_embedding_dim)
        temp_enc = torch.randn(settings.temporal_encoding_dim)

        model_input = ModelInput(
            event_embeddings=event_emb,
            weather_embeddings=weather_emb,
            historical_sequence=hist_seq,
            temporal_encoding=temp_enc,
        )

        # Move to CPU (default device for tests)
        model_input_cpu = model_input.to(torch.device("cpu"))

        assert model_input_cpu.event_embeddings.device.type == "cpu"
        assert model_input_cpu.weather_embeddings.device.type == "cpu"
        assert model_input_cpu.historical_sequence.device.type == "cpu"
        assert model_input_cpu.temporal_encoding.device.type == "cpu"


class TestTensorPreprocessor:
    """Tests for the main TensorPreprocessor class - Requirement 4.9."""

    def test_preprocess_empty_data(self):
        """Test preprocessing with empty data - Requirement 4.9."""
        preprocessor = TensorPreprocessor()

        event_data = EventCalendarData(events=[], last_updated=datetime.utcnow())
        weather_data = WeatherData(current_conditions=None, forecast=[], last_updated=datetime.utcnow())
        historical_data = HistoricalAvailabilityData(records=[], location_id="test")
        pred_time = datetime(2024, 6, 15, 18, 0, 0)

        result = preprocessor.preprocess(event_data, weather_data, historical_data, pred_time)

        assert isinstance(result, ModelInput)
        assert result.event_embeddings.shape == torch.Size([settings.event_embedding_dim])
        assert result.weather_embeddings.shape == torch.Size([settings.weather_embedding_dim])
        assert result.historical_sequence.shape == torch.Size(
            [settings.historical_sequence_length, settings.event_embedding_dim]
        )
        assert result.temporal_encoding.shape == torch.Size([settings.temporal_encoding_dim])

    def test_preprocess_with_data(self):
        """Test preprocessing with populated data."""
        preprocessor = TensorPreprocessor()

        # Create event data
        event = CalendarEvent(
            event_id=uuid4(),
            title="Test Concert",
            event_type=EventType.CONCERT,
            expected_attendance=500,
            location=Location(
                venue_id="test_venue",
                latitude=40.7128,
                longitude=-74.0060,
                capacity=1000,
            ),
            start_time=datetime(2024, 6, 15, 18, 0, 0),
            end_time=datetime(2024, 6, 15, 23, 0, 0),
            is_outdoor=True,
        )
        event_data = EventCalendarData(events=[event], last_updated=datetime.utcnow())

        # Create weather data
        conditions = WeatherConditions(
            temperature=25.5,
            humidity=65.0,
            precipitation_probability=0.3,
            wind_speed=5.2,
            weather_type=WeatherType.CLEAR,
        )
        weather_data = WeatherData(current_conditions=conditions, forecast=[], last_updated=datetime.utcnow())

        # Create historical data
        record = AvailabilityRecord(
            timestamp=datetime(2024, 6, 15, 18, 0, 0),
            available_slots=150,
            total_slots=500,
            utilization_rate=0.7,
            contextual_factors=ContextualFactors(),
        )
        historical_data = HistoricalAvailabilityData(records=[record], location_id="test_location")

        pred_time = datetime(2024, 6, 15, 18, 0, 0)

        result = preprocessor.preprocess(event_data, weather_data, historical_data, pred_time)

        assert isinstance(result, ModelInput)
        assert result.event_embeddings.shape == torch.Size([settings.event_embedding_dim])
        assert result.weather_embeddings.shape == torch.Size([settings.weather_embedding_dim])
        assert result.historical_sequence.shape == torch.Size(
            [settings.historical_sequence_length, settings.event_embedding_dim]
        )
        assert result.temporal_encoding.shape == torch.Size([settings.temporal_encoding_dim])

    def test_create_model_input(self):
        """Test creating ModelInput from components."""
        preprocessor = TensorPreprocessor()

        # Create dummy inputs
        event_emb = torch.randn(settings.event_embedding_dim)
        weather_emb = torch.randn(settings.weather_embedding_dim)
        hist_seq = torch.randn(settings.historical_sequence_length, settings.event_embedding_dim)
        temp_enc = torch.randn(settings.temporal_encoding_dim)

        model_input = preprocessor.create_model_input(event_emb, weather_emb, hist_seq, temp_enc)

        assert isinstance(model_input, ModelInput)
        assert model_input.event_embeddings.shape == torch.Size([settings.event_embedding_dim])
        assert model_input.weather_embeddings.shape == torch.Size([settings.weather_embedding_dim])
        assert model_input.historical_sequence.shape == torch.Size(
            [settings.historical_sequence_length, settings.event_embedding_dim]
        )
        assert model_input.temporal_encoding.shape == torch.Size([settings.temporal_encoding_dim])

    def test_validate_input(self):
        """Test input validation - Requirement 4.9."""
        preprocessor = TensorPreprocessor()

        # Valid inputs
        event_emb = torch.randn(settings.event_embedding_dim)
        weather_emb = torch.randn(settings.weather_embedding_dim)
        hist_seq = torch.randn(settings.historical_sequence_length, settings.event_embedding_dim)
        temp_enc = torch.randn(settings.temporal_encoding_dim)

        assert preprocessor.validate_input(event_emb, weather_emb, hist_seq, temp_enc) is True

        # Invalid: NaN values
        event_emb_nan = torch.randn(settings.event_embedding_dim)
        event_emb_nan[0] = float("nan")

        with pytest.raises(ValueError, match="NaN detected"):
            preprocessor.validate_input(event_emb_nan, weather_emb, hist_seq, temp_enc)

        # Invalid: Wrong dimensions
        event_emb_wrong = torch.randn(settings.event_embedding_dim + 10)

        with pytest.raises(ValueError, match="dim mismatch"):
            preprocessor.validate_input(event_emb_wrong, weather_emb, hist_seq, temp_enc)


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_preprocessor(self):
        """Test create_preprocessor function."""
        from backend.cat.preprocessing.encoders import create_preprocessor

        preprocessor = create_preprocessor(device="cpu")

        assert isinstance(preprocessor, TensorPreprocessor)

    def test_encode_events(self):
        """Test encode_events convenience function."""
        from backend.cat.preprocessing.encoders import encode_events

        event_data = EventCalendarData(events=[], last_updated=datetime.utcnow())

        embedding = encode_events(event_data)

        assert embedding.shape[0] == settings.event_embedding_dim

    def test_encode_weather(self):
        """Test encode_weather convenience function."""
        from backend.cat.preprocessing.encoders import encode_weather

        weather_data = WeatherData(current_conditions=None, forecast=[], last_updated=datetime.utcnow())

        embedding = encode_weather(weather_data)

        assert embedding.shape[0] == settings.weather_embedding_dim

    def test_encode_historical(self):
        """Test encode_historical convenience function."""
        from backend.cat.preprocessing.encoders import encode_historical

        historical_data = HistoricalAvailabilityData(records=[], location_id="test")

        sequence = encode_historical(historical_data)

        assert sequence.shape[0] == settings.historical_sequence_length


if __name__ == "__main__":
    pytest.main([__file__, "-v"])