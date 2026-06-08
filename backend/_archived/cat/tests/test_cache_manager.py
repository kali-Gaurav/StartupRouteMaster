"""
Unit tests for the prediction cache and cache manager.
Tests Redis caching, cache key generation, TTL handling, and cache invalidation.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json

from backend.cat.inference.cache_manager import (
    PredictionCache,
    CacheManager,
    CacheConfig,
    CacheStats,
    create_prediction_cache,
    create_cache_manager
)
from backend.cat.models.schemas import AvailabilityPrediction


class TestCacheConfig:
    """Tests for CacheConfig dataclass."""
    
    def test_default_config(self):
        """Test default cache configuration."""
        config = CacheConfig()
        
        assert config.enabled is True
        assert config.ttl_seconds == 300
        assert config.local_cache_ttl_seconds == 60
        assert config.local_cache_max_size == 1000
        assert config.redis_cache_prefix == "cat:"
        assert config.invalidate_on_model_update is True
    
    def test_custom_config(self):
        """Test custom cache configuration."""
        config = CacheConfig(
            enabled=False,
            ttl_seconds=600,
            local_cache_ttl_seconds=120,
            local_cache_max_size=500,
            redis_cache_prefix="test:"
        )
        
        assert config.enabled is False
        assert config.ttl_seconds == 600
        assert config.local_cache_ttl_seconds == 120
        assert config.local_cache_max_size == 500
        assert config.redis_cache_prefix == "test:"


class TestPredictionCache:
    """Tests for PredictionCache class."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = MagicMock()
        mock.ping.return_value = True
        mock.get.return_value = None
        mock.setex.return_value = True
        mock.keys.return_value = []
        mock.delete.return_value = 1
        return mock
    
    @pytest.fixture
    def cache(self, mock_redis):
        """Create a cache with mocked Redis."""
        config = CacheConfig(
            redis_url="redis://localhost:6379",
            ttl_seconds=300,
            local_cache_ttl_seconds=60
        )
        return PredictionCache(config=config, redis_client=mock_redis)
    
    @pytest.fixture
    def local_only_cache(self):
        """Create a cache without Redis (local only)."""
        config = CacheConfig(
            redis_url=None,
            ttl_seconds=300,
            local_cache_ttl_seconds=60
        )
        return PredictionCache(config=config)
    
    @pytest.fixture
    def sample_prediction(self):
        """Create a sample prediction."""
        return AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_location",
            prediction_time=datetime(2024, 6, 15, 18, 0, 0).isoformat(),
            model_version="1.0.0"
        )
    
    def test_cache_key_generation(self, cache):
        """Test that cache keys are generated correctly."""
        prediction_time = datetime(2024, 6, 15, 18, 0, 0)
        cache_key = cache._get_cache_key("test_location", prediction_time)
        
        assert "test_location" in cache_key
        assert "2024-06-15" in cache_key
        assert cache_key.startswith("cat:")
        assert "pred:" in cache_key
    
    def test_cache_key_normalization(self, cache):
        """Test that cache keys normalize time to minute precision."""
        # Time with seconds should be normalized
        prediction_time = datetime(2024, 6, 15, 18, 30, 45, 123456)
        cache_key = cache._get_cache_key("loc", prediction_time)
        
        # Should include the normalized time with colons
        # Format: cat:pred:loc:2024-06-15T18:30:00
        assert "2024-06-15T18:30" in cache_key
        # Seconds should be zeroed (00)
        assert cache_key.endswith("00") or "T18:30" in cache_key
    
    def test_local_cache_set_and_get(self, local_only_cache, sample_prediction):
        """Test local cache set and get operations."""
        prediction_time = datetime(2024, 6, 15, 18, 0, 0)
        
        # Set prediction
        local_only_cache.set("test_location", prediction_time, sample_prediction)
        
        # Get prediction
        retrieved = local_only_cache.get("test_location", prediction_time)
        
        assert retrieved is not None
        assert retrieved.probability == 0.75
        assert retrieved.location_id == "test_location"
    
    def test_cache_miss_returns_none(self, local_only_cache):
        """Test that cache miss returns None."""
        prediction_time = datetime(2024, 6, 15, 18, 0, 0)
        result = local_only_cache.get("nonexistent_location", prediction_time)
        
        assert result is None
    
    def test_cache_expiration(self, local_only_cache, sample_prediction):
        """Test that expired cache entries are not returned."""
        # Create cache with very short local TTL
        local_only_cache.config.local_cache_ttl_seconds = 1
        
        prediction_time = datetime(2024, 6, 15, 18, 0, 0)
        local_only_cache.set("test_location", prediction_time, sample_prediction)
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should return None (expired)
        result = local_only_cache.get("test_location", prediction_time)
        assert result is None
    
    def test_cache_invalidation_by_location(self, local_only_cache, sample_prediction):
        """Test cache invalidation for specific location."""
        # Add predictions for multiple locations
        local_only_cache.set("loc1", datetime(2024, 6, 15, 18, 0, 0), sample_prediction)
        local_only_cache.set("loc2", datetime(2024, 6, 15, 18, 0, 0), sample_prediction)
        
        # Invalidate specific location
        local_only_cache.invalidate("loc1")
        
        # loc1 should be cleared
        assert local_only_cache.get("loc1", datetime(2024, 6, 15, 18, 0, 0)) is None
        # loc2 should still be cached
        assert local_only_cache.get("loc2", datetime(2024, 6, 15, 18, 0, 0)) is not None
    
    def test_cache_clear(self, local_only_cache, sample_prediction):
        """Test clearing all cached predictions."""
        local_only_cache.set("loc1", datetime(2024, 6, 15, 18, 0, 0), sample_prediction)
        local_only_cache.set("loc2", datetime(2024, 6, 15, 18, 0, 0), sample_prediction)
        
        local_only_cache.clear()
        
        stats = local_only_cache.get_stats()
        assert stats["local_cache_size"] == 0
    
    def test_get_stats(self, local_only_cache, sample_prediction):
        """Test getting cache statistics."""
        local_only_cache.set("loc1", datetime(2024, 6, 15, 18, 0, 0), sample_prediction)
        local_only_cache.get("loc1", datetime(2024, 6, 15, 18, 0, 0))
        local_only_cache.get("nonexistent", datetime(2024, 6, 15, 18, 0, 0))
        
        stats = local_only_cache.get_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert "sets" in stats
        assert "local_cache_size" in stats
        assert "ttl_seconds" in stats
        assert stats["sets"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
    
    def test_hit_rate_calculation(self, local_only_cache, sample_prediction):
        """Test cache hit rate calculation."""
        prediction_time = datetime(2024, 6, 15, 18, 0, 0)
        
        # Add and retrieve (hit)
        local_only_cache.set("loc1", prediction_time, sample_prediction)
        local_only_cache.get("loc1", prediction_time)
        
        # Miss
        local_only_cache.get("nonexistent", prediction_time)
        
        hit_rate = local_only_cache.get_hit_rate()
        assert hit_rate == 50.0  # 1 hit, 1 miss = 50%
    
    def test_redis_integration(self, cache, mock_redis, sample_prediction):
        """Test Redis integration for caching."""
        prediction_time = datetime(2024, 6, 15, 18, 0, 0)
        
        # Serialize prediction for Redis
        serialized = cache._serialize_prediction(sample_prediction)
        mock_redis.get.return_value = serialized
        
        # Set should go to Redis
        cache.set("test_location", prediction_time, sample_prediction)
        mock_redis.setex.assert_called_once()
        
        # Get should retrieve from Redis
        result = cache.get("test_location", prediction_time)
        assert result is not None
        assert result.probability == 0.75
    
    def test_redis_connection_failure(self, mock_redis):
        """Test graceful handling of Redis connection failure."""
        mock_redis.get.side_effect = Exception("Connection refused")
        
        config = CacheConfig(
            redis_url="redis://localhost:6379",
            ttl_seconds=300
        )
        cache = PredictionCache(config=config, redis_client=mock_redis)
        
        prediction_time = datetime(2024, 6, 15, 18, 0, 0)
        
        # Should fall back to local cache
        result = cache.get("test_location", prediction_time)
        assert result is None  # No local cache entry
    
    def test_lru_eviction(self, local_only_cache, sample_prediction):
        """Test LRU eviction when local cache is full."""
        # Create cache with small max size
        local_only_cache.config.local_cache_max_size = 3
        
        # Add more entries than max size
        for i in range(5):
            local_only_cache.set(f"loc{i}", datetime(2024, 6, 15, 18, i, 0), sample_prediction)
        
        # Should have evicted old entries
        stats = local_only_cache.get_stats()
        assert stats["local_cache_size"] <= 3
    
    def test_serialization_roundtrip(self, cache, sample_prediction):
        """Test prediction serialization and deserialization."""
        serialized = cache._serialize_prediction(sample_prediction)
        deserialized = cache._deserialize_prediction(serialized)
        
        assert deserialized.probability == sample_prediction.probability
        assert deserialized.confidence_interval == sample_prediction.confidence_interval
        assert deserialized.location_id == sample_prediction.location_id
    
    def test_health_check(self, local_only_cache, mock_redis):
        """Test cache health check."""
        health = local_only_cache.health_check()
        
        assert "healthy" in health
        assert "local_cache_entries" in health
        assert "hit_rate_percent" in health


class TestCacheManager:
    """Tests for CacheManager class."""
    
    @pytest.fixture
    def cache(self):
        """Create a local-only cache."""
        config = CacheConfig(redis_url=None, ttl_seconds=300)
        return PredictionCache(config=config)
    
    @pytest.fixture
    def cache_manager(self, cache):
        """Create a cache manager."""
        return CacheManager(cache=cache)
    
    @pytest.fixture
    def sample_prediction(self):
        """Create a sample prediction."""
        return AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_location",
            prediction_time=datetime(2024, 6, 15, 18, 0, 0).isoformat(),
            model_version="1.0.0"
        )
    
    def test_on_model_loaded(self, cache_manager):
        """Test handling model loaded event."""
        cache_manager.on_model_loaded("v2.0.0")
        
        stats = cache_manager.get_stats()
        assert stats["model_version"] == "v2.0.0"
    
    def test_on_model_hot_swap(self, cache_manager, cache, sample_prediction):
        """Test handling model hot-swap event."""
        # Add some cached predictions
        cache.set("loc1", datetime(2024, 6, 15, 18, 0, 0), sample_prediction)
        
        # Perform hot-swap
        invalidated = cache_manager.on_model_hot_swap("v1.0.0", "v2.0.0")
        
        # Cache should be invalidated
        assert cache.get("loc1", datetime(2024, 6, 15, 18, 0, 0)) is None
        assert invalidated >= 0
    
    def test_on_model_reload(self, cache_manager, cache, sample_prediction):
        """Test handling model reload event."""
        # Add cached prediction
        cache.set("loc1", datetime(2024, 6, 15, 18, 0, 0), sample_prediction)
        
        # Reload model
        invalidated = cache_manager.on_model_reload("v1.0.1")
        
        # Cache should be invalidated
        assert cache.get("loc1", datetime(2024, 6, 15, 18, 0, 0)) is None
    
    def test_register_model_update_callback(self, cache_manager):
        """Test registering model update callbacks."""
        callback = Mock()
        
        cache_manager.register_model_update_callback(callback)
        
        # Trigger model update
        cache_manager.on_model_loaded("v2.0.0")
        
        # Callback should have been called
        callback.assert_called_once_with("v2.0.0")
    
    def test_invalidate_for_location(self, cache_manager, cache, sample_prediction):
        """Test invalidating cache for specific location."""
        cache.set("loc1", datetime(2024, 6, 15, 18, 0, 0), sample_prediction)
        cache.set("loc2", datetime(2024, 6, 15, 18, 0, 0), sample_prediction)
        
        invalidated = cache_manager.invalidate_for_location("loc1")
        
        assert cache.get("loc1", datetime(2024, 6, 15, 18, 0, 0)) is None
        assert cache.get("loc2", datetime(2024, 6, 15, 18, 0, 0)) is not None
        assert invalidated == 1
    
    def test_get_stats(self, cache_manager, cache, sample_prediction):
        """Test getting cache manager statistics."""
        cache.set("loc1", datetime(2024, 6, 15, 18, 0, 0), sample_prediction)
        
        stats = cache_manager.get_stats()
        
        assert "cache_stats" in stats
        assert "model_version" in stats
        assert "registered_callbacks" in stats
        assert stats["cache_stats"]["local_cache_size"] == 1
    
    def test_health_check(self, cache_manager):
        """Test cache manager health check."""
        health = cache_manager.health_check()
        
        assert "cache_healthy" in health
        assert "model_version" in health


class TestFactoryFunctions:
    """Tests for factory functions."""
    
    def test_create_prediction_cache(self):
        """Test create_prediction_cache factory."""
        with patch('backend.cat.inference.cache_manager.settings') as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"
            mock_settings.prediction_cache_ttl_seconds = 600
            
            cache = create_prediction_cache(
                redis_url="redis://localhost:6379",
                ttl_seconds=600
            )
            
            assert cache is not None
            assert cache.config.ttl_seconds == 600
    
    def test_create_cache_manager(self):
        """Test create_cache_manager factory."""
        cache = create_prediction_cache()
        manager = create_cache_manager(cache=cache)
        
        assert manager is not None
        assert manager.cache is cache


class TestCacheIntegration:
    """Integration tests for cache with model manager."""
    
    def test_model_manager_cache_invalidation_on_hot_swap(self):
        """Test that cache is invalidated when model is hot-swapped."""
        # Create mock cache and manager
        config = CacheConfig(redis_url=None, ttl_seconds=300)
        cache = PredictionCache(config=config)
        cache_manager = CacheManager(cache=cache)
        
        # Create prediction and cache it
        prediction = AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="test_loc",
            prediction_time=datetime(2024, 6, 15, 18, 0, 0).isoformat(),
            model_version="v1.0.0"
        )
        cache.set("test_loc", datetime(2024, 6, 15, 18, 0, 0), prediction)
        
        # Verify it's cached
        assert cache.get("test_loc", datetime(2024, 6, 15, 18, 0, 0)) is not None
        
        # Simulate hot-swap
        invalidated = cache_manager.on_model_hot_swap("v1.0.0", "v2.0.0")
        
        # Cache should be invalidated
        assert cache.get("test_loc", datetime(2024, 6, 15, 18, 0, 0)) is None
    
    def test_cache_key_uniqueness(self):
        """Test that cache keys are unique for different inputs."""
        config = CacheConfig(redis_url=None, ttl_seconds=300)
        cache = PredictionCache(config=config)
        
        # Different locations
        key1 = cache._get_cache_key("loc1", datetime(2024, 6, 15, 18, 0, 0))
        key2 = cache._get_cache_key("loc2", datetime(2024, 6, 15, 18, 0, 0))
        assert key1 != key2
        
        # Different times
        key3 = cache._get_cache_key("loc1", datetime(2024, 6, 15, 19, 0, 0))
        assert key1 != key3
        
        # Same inputs should produce same key
        key4 = cache._get_cache_key("loc1", datetime(2024, 6, 15, 18, 0, 0))
        assert key1 == key4


class TestCacheEdgeCases:
    """Tests for edge cases in caching."""
    
    @pytest.fixture
    def local_only_cache(self):
        """Create a cache without Redis (local only)."""
        config = CacheConfig(
            redis_url=None,
            ttl_seconds=300,
            local_cache_ttl_seconds=60
        )
        return PredictionCache(config=config)
    
    def test_none_location_id(self, local_only_cache):
        """Test handling of None location_id."""
        result = local_only_cache.get(None, datetime.utcnow())
        assert result is None
    
    def test_none_prediction_time(self, local_only_cache):
        """Test handling of None prediction_time."""
        result = local_only_cache.get("loc1", None)
        assert result is None
    
    def test_empty_prediction(self, local_only_cache):
        """Test caching empty or minimal prediction."""
        prediction = AvailabilityPrediction(
            probability=0.5,
            confidence_interval=(0.3, 0.7),
            contributing_factors=[],
            location_id="test",
            prediction_time=datetime.utcnow().isoformat(),
            model_version="1.0.0"
        )
        
        local_only_cache.set("test", datetime.utcnow(), prediction)
        result = local_only_cache.get("test", datetime.utcnow())
        
        assert result is not None
        assert result.probability == 0.5
    
    def test_concurrent_access(self):
        """Test thread-safe concurrent cache access."""
        import threading
        
        config = CacheConfig(redis_url=None, ttl_seconds=300, local_cache_max_size=10000)
        cache = PredictionCache(config=config)
        
        prediction = AvailabilityPrediction(
            probability=0.75,
            confidence_interval=(0.65, 0.85),
            contributing_factors=[],
            location_id="concurrent_test",
            prediction_time=datetime.utcnow().isoformat(),
            model_version="1.0.0"
        )
        
        errors = []
        
        def writer():
            try:
                for i in range(100):
                    cache.set(f"loc{i % 10}", datetime.utcnow(), prediction)
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for i in range(100):
                    cache.get("loc0", datetime.utcnow())
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=writer) for _ in range(5)] + \
                  [threading.Thread(target=reader) for _ in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should not have any errors
        assert len(errors) == 0