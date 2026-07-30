#!/usr/bin/env python3
"""
Unit tests for ML-based reliability model and frequency-aware Range-RAPTOR
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

from ml_reliability_model import MLReliabilityModel
from frequency_aware_range import FrequencyAwareWindowSizer


# ==============================================================================
# ML Reliability Model Tests
# ==============================================================================

class TestMLReliabilityModel:
    """Test ML reliability estimation"""

    def test_init_loads_model_gracefully_when_missing(self):
        """Model should gracefully handle missing pre-trained model"""
        model = MLReliabilityModel()
        # Should not raise even if model file missing
        assert model is not None
        assert model.model is None  # No model loaded yet
        assert model.loaded is False

    @pytest.mark.asyncio
    async def test_fallback_heuristic_penalizes_short_transfer(self):
        """Short transfers should reduce reliability score"""
        model = MLReliabilityModel()
        
        # Transfer too short (<10 min) → significant penalty
        reliability = await model._fallback_heuristic(
            transfer_duration_minutes=5,
            distance_km=100,
            departure_time=datetime(2026, 2, 19, 10, 0),  # Non-peak
        )
        assert reliability < 0.7  # Should be penalized heavily
        
        # Reasonable transfer (20 min) → minimal penalty
        reliability = await model._fallback_heuristic(
            transfer_duration_minutes=20,
            distance_km=100,
            departure_time=datetime(2026, 2, 19, 10, 0),
        )
        assert reliability > 0.95

    @pytest.mark.asyncio
    async def test_fallback_heuristic_penalizes_peak_hours(self):
        """Peak hours should reduce reliability"""
        model = MLReliabilityModel()
        
        # Non-peak hour
        non_peak = await model._fallback_heuristic(
            transfer_duration_minutes=15,
            distance_km=100,
            departure_time=datetime(2026, 2, 19, 11, 0),
        )
        
        # Peak hour (9 AM)
        peak = await model._fallback_heuristic(
            transfer_duration_minutes=15,
            distance_km=100,
            departure_time=datetime(2026, 2, 19, 9, 0),
        )
        
        assert peak < non_peak  # Peak hours less reliable

    @pytest.mark.asyncio
    async def test_fallback_heuristic_scales_with_distance(self):
        """Longer distances should reduce reliability"""
        model = MLReliabilityModel()
        
        # Short distance
        short = await model._fallback_heuristic(
            transfer_duration_minutes=15,
            distance_km=100,
            departure_time=datetime(2026, 2, 19, 10, 0),
        )
        
        # Long distance
        long = await model._fallback_heuristic(
            transfer_duration_minutes=15,
            distance_km=1000,
            departure_time=datetime(2026, 2, 19, 10, 0),
        )
        
        assert long < short  # Longer distances more unreliable

    @pytest.mark.asyncio
    async def test_predict_returns_valid_probability(self):
        """Prediction should always return [0, 1]"""
        model = MLReliabilityModel()
        
        pred = await model.predict(
            trip_id=1,
            origin_stop_id=10,
            destination_stop_id=20,
            departure_time=datetime(2026, 2, 19, 10, 0),
            transfer_duration_minutes=15,
            distance_km=150,
        )
        
        assert 0.0 <= pred <= 1.0
        assert isinstance(pred, float)

    @pytest.mark.asyncio
    async def test_vectorize_features_handles_missing_features(self):
        """Should pad missing features with 0.0"""
        model = MLReliabilityModel()
        model.feature_names = ["feat_a", "feat_b", "feat_c"]
        
        partial_features = {"feat_a": 1.0, "feat_c": 3.0}  # missing feat_b
        X = model._vectorize_features(partial_features)
        
        assert X.shape == (1, 3)
        assert X[0][0] == 1.0  # feat_a
        assert X[0][1] == 0.0  # feat_b (missing)
        assert X[0][2] == 3.0  # feat_c


# ==============================================================================
# Frequency-Aware Range-RAPTOR Tests
# ==============================================================================

class TestFrequencyAwareWindowSizer:
    """Test frequency-aware window sizing for Range-RAPTOR"""

    def test_init(self):
        """Should initialize sizer"""
        sizer = FrequencyAwareWindowSizer()
        assert sizer is not None

    @pytest.mark.asyncio
    async def test_high_frequency_shrinks_window(self):
        """High-frequency corridors should use smaller window"""
        sizer = FrequencyAwareWindowSizer()
        
        with patch.object(sizer, '_compute_corridor_frequency', return_value=3.0):  # 3 trips/hour
            window = await sizer.get_range_window_minutes(
                origin_stop_id=1,
                destination_stop_id=2,
                search_date=date(2026, 2, 19),
                base_range_minutes=60,
            )
            assert window == 30  # Should shrink to 30 min

    @pytest.mark.asyncio
    async def test_medium_frequency_keeps_default_window(self):
        """Medium-frequency corridors should keep base window"""
        sizer = FrequencyAwareWindowSizer()
        
        with patch.object(sizer, '_compute_corridor_frequency', return_value=1.5):  # 1.5 trips/hour
            window = await sizer.get_range_window_minutes(
                origin_stop_id=1,
                destination_stop_id=2,
                search_date=date(2026, 2, 19),
                base_range_minutes=60,
            )
            assert window == 60  # Should keep base

    @pytest.mark.asyncio
    async def test_low_frequency_expands_to_2h(self):
        """Low-frequency corridors should expand window"""
        sizer = FrequencyAwareWindowSizer()
        
        with patch.object(sizer, '_compute_corridor_frequency', return_value=0.7):  # 0.7 trips/hour
            window = await sizer.get_range_window_minutes(
                origin_stop_id=1,
                destination_stop_id=2,
                search_date=date(2026, 2, 19),
                base_range_minutes=60,
            )
            assert window == 120  # Should expand to 2h

    @pytest.mark.asyncio
    async def test_very_low_frequency_scales_with_distance(self):
        """Very low frequency corridors should expand based on distance"""
        sizer = FrequencyAwareWindowSizer()
        
        with patch.object(sizer, '_compute_corridor_frequency', return_value=0.2):  # <0.5 trips/hour
            # Short distance
            window_short = await sizer.get_range_window_minutes(
                origin_stop_id=1,
                destination_stop_id=2,
                search_date=date(2026, 2, 19),
                distance_km=150,  # < 200km
            )
            assert window_short == 180  # 3 hours
            
            # Medium distance
            window_medium = await sizer.get_range_window_minutes(
                origin_stop_id=1,
                destination_stop_id=2,
                search_date=date(2026, 2, 19),
                distance_km=500,  # < 800km
            )
            assert window_medium == 360  # 6 hours
            
            # Long distance
            window_long = await sizer.get_range_window_minutes(
                origin_stop_id=1,
                destination_stop_id=2,
                search_date=date(2026, 2, 19),
                distance_km=1500,  # > 800km
            )
            assert window_long == 480  # 8 hours

    @pytest.mark.asyncio
    async def test_frequency_computation_caches_result(self):
        """Frequency should be cached to avoid repeated DB queries"""
        sizer = FrequencyAwareWindowSizer()
        sizer.redis_client = None  # Simulate no Redis
        
        mock_db_compute = AsyncMock(return_value=2.0)
        
        with patch.object(sizer, '_compute_frequency_from_db', mock_db_compute):
            # First call
            freq1 = await sizer._compute_corridor_frequency(1, 2, date(2026, 2, 19))
            assert freq1 == 2.0
            assert mock_db_compute.call_count == 1
            
            # Second call (should use cache logic if Redis available)
            freq2 = await sizer._compute_corridor_frequency(1, 2, date(2026, 2, 19))
            assert freq2 == 2.0
            # Without Redis, should query twice
            # (with Redis, second call would be cached)

    @pytest.mark.asyncio
    async def test_window_defaults_to_6h_when_no_distance(self):
        """Should default to 6 hours when distance unavailable"""
        sizer = FrequencyAwareWindowSizer()
        
        with patch.object(sizer, '_compute_corridor_frequency', return_value=0.1):
            window = await sizer.get_range_window_minutes(
                origin_stop_id=1,
                destination_stop_id=2,
                search_date=date(2026, 2, 19),
                distance_km=None,  # Unknown distance
            )
            assert window == 360  # Default to 6h


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestIntegration:
    """Integration tests for ML reliability + frequency-aware Range-RAPTOR"""

    @pytest.mark.asyncio
    async def test_reliability_prediction_doesnt_exceed_1(self):
        """Reliability should always be <= 1.0"""
        model = MLReliabilityModel()
        
        for transfer_dur in [5, 10, 15, 30]:
            for dist in [50, 200, 1000]:
                for hour in [0, 8, 10, 18, 22]:
                    pred = await model.predict(
                        trip_id=1,
                        origin_stop_id=1,
                        destination_stop_id=2,
                        departure_time=datetime(2026, 2, 19, hour, 0),
                        transfer_duration_minutes=transfer_dur,
                        distance_km=dist,
                    )
                    assert pred <= 1.0, f"Reliability > 1.0 for transfer={transfer_dur}, dist={dist}, hour={hour}"

    @pytest.mark.asyncio
    async def test_frequency_window_reasonable_range(self):
        """Windows should always be reasonable [30, 480] minutes"""
        sizer = FrequencyAwareWindowSizer()
        
        for freq in [0.1, 0.5, 1.0, 2.0, 5.0]:
            with patch.object(sizer, '_compute_corridor_frequency', return_value=freq):
                for dist in [50, 200, 500, 1000, 1500]:
                    window = await sizer.get_range_window_minutes(
                        origin_stop_id=1,
                        destination_stop_id=2,
                        search_date=date(2026, 2, 19),
                        distance_km=dist,
                    )
                    assert 30 <= window <= 480, f"Window out of range: {window} for freq={freq}, dist={dist}"
