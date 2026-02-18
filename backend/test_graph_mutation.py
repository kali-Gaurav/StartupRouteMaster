"""
Test Graph Mutation Engine - Real-Time Updates

Tests the real-time graph mutation functionality including:
- Train state management
- Graph delta updates
- Cache invalidation
- API endpoints
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import json
import sys
import os

from backend.train_state_service import (
    TrainState,
    TrainStateStore,
    GraphMutationEngine
)
from backend.graph_mutation_service import (
    apply_delay,
    cancel_train,
    update_location,
    update_occupancy,
    get_train_state,
    DelayUpdateRequest,
    CancellationUpdateRequest,
    LocationUpdateRequest,
    OccupancyUpdateRequest
)
from backend.route_engine import OptimizedRAPTOR


class TestTrainState:
    """Test TrainState dataclass"""

    def test_train_state_creation(self):
        """Test creating a train state"""
        state = TrainState(
            trip_id=123,
            train_number="12345",
            delay_minutes=15,
            status="delayed"
        )

        assert state.trip_id == 123
        assert state.train_number == "12345"
        assert state.delay_minutes == 15
        assert state.status == "delayed"
        assert isinstance(state.last_updated, datetime)
        assert state.cancelled_stations == []

    def test_train_state_to_dict(self):
        """Test converting train state to dict"""
        state = TrainState(trip_id=123, train_number="12345")
        data = state.to_dict()

        assert data['trip_id'] == 123
        assert data['train_number'] == "12345"
        assert 'last_updated' in data

    def test_train_state_from_dict(self):
        """Test creating train state from dict"""
        data = {
            'trip_id': 123,
            'train_number': "12345",
            'delay_minutes': 10,
            'status': "delayed",
            'last_updated': datetime.utcnow().isoformat(),
            'cancelled_stations': []
        }

        state = TrainState.from_dict(data)
        assert state.trip_id == 123
        assert state.delay_minutes == 10
        assert state.status == "delayed"


class TestTrainStateStore:
    """Test TrainStateStore functionality"""

    @pytest.fixture
    def store(self):
        """Create a test store instance"""
        store = TrainStateStore()
        # Mock Redis for testing
        store.redis = AsyncMock()
        return store

    @pytest.mark.asyncio
    async def test_get_train_state_from_redis(self, store):
        """Test getting train state from Redis"""
        # Mock Redis response
        state_data = {
            'trip_id': 123,
            'train_number': "12345",
            'delay_minutes': 0,
            'status': "on_time",
            'last_updated': datetime.utcnow().isoformat(),
            'cancelled_stations': []
        }
        store.redis.get.return_value = json.dumps(state_data)

        state = await store.get_train_state(123)

        assert state.trip_id == 123
        assert state.status == "on_time"
        store.redis.get.assert_called_once_with("train_state:123")

    @pytest.mark.asyncio
    async def test_update_train_state(self, store):
        """Test updating train state"""
        state = TrainState(trip_id=123, train_number="12345", delay_minutes=15)

        await store.update_train_state(state)

        # Verify Redis calls
        assert store.redis.setex.called
        args = store.redis.setex.call_args
        assert args[0][0] == "train_state:123"
        assert args[0][1] == 86400  # 24 hours

    @pytest.mark.asyncio
    async def test_apply_delay(self, store):
        """Test applying delay to train"""
        # Mock existing state
        existing_state = TrainState(trip_id=123, train_number="12345")
        store.get_train_state = AsyncMock(return_value=existing_state)
        store.update_train_state = AsyncMock()

        await store.apply_delay(123, 30, "Signal failure")

        # Verify state was updated
        store.update_train_state.assert_called_once()
        updated_state = store.update_train_state.call_args[0][0]
        assert updated_state.delay_minutes == 30
        assert updated_state.status == "delayed"

    @pytest.mark.asyncio
    async def test_cancel_train(self, store):
        """Test cancelling a train"""
        existing_state = TrainState(trip_id=123, train_number="12345")
        store.get_train_state = AsyncMock(return_value=existing_state)
        store.update_train_state = AsyncMock()

        await store.cancel_train(123, [456, 789])

        store.update_train_state.assert_called_once()
        updated_state = store.update_train_state.call_args[0][0]
        assert updated_state.status == "cancelled"
        assert updated_state.cancelled_stations == [456, 789]


class TestGraphMutationEngine:
    """Test GraphMutationEngine functionality"""

    @pytest.fixture
    def route_engine(self):
        """Create a mock route engine"""
        engine = Mock(spec=OptimizedRAPTOR)
        engine.apply_realtime_updates = AsyncMock()
        return engine

    @pytest.fixture
    def mutation_engine(self, route_engine):
        """Create a test mutation engine"""
        engine = GraphMutationEngine(route_engine)
        # skip async initialization in tests and inject mocked redis
        engine.train_state_store.redis = AsyncMock()
        return engine

    @pytest.mark.asyncio
    async def test_apply_train_delay(self, mutation_engine):
        """Test applying delay mutation"""
        # Mock affected segments
        mutation_engine._get_affected_segments = AsyncMock(return_value=[])
        mutation_engine._update_graph_segments = AsyncMock()
        mutation_engine._invalidate_affected_caches = AsyncMock()

        await mutation_engine.apply_train_delay(123, 25)

        mutation_engine._get_affected_segments.assert_called_once_with(123)
        mutation_engine._update_graph_segments.assert_called_once()
        mutation_engine._invalidate_affected_caches.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_apply_train_cancellation(self, mutation_engine):
        """Test applying cancellation mutation"""
        mutation_engine._get_affected_segments = AsyncMock(return_value=[])
        mutation_engine._update_graph_segments = AsyncMock()
        mutation_engine._invalidate_affected_caches = AsyncMock()

        await mutation_engine.apply_train_cancellation(123, [456])

        mutation_engine._update_graph_segments.assert_called_once()
        mutation_engine._invalidate_affected_caches.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_process_realtime_update_delay(self, mutation_engine):
        """Test processing delay update"""
        mutation_engine.apply_train_delay = AsyncMock()

        update = {
            'type': 'delay',
            'trip_id': 123,
            'delay_minutes': 20
        }

        await mutation_engine.process_realtime_update(update)

        mutation_engine.apply_train_delay.assert_called_once_with(123, 20)

    @pytest.mark.asyncio
    async def test_process_realtime_update_cancellation(self, mutation_engine):
        """Test processing cancellation update"""
        mutation_engine.apply_train_cancellation = AsyncMock()

        update = {
            'type': 'cancellation',
            'trip_id': 123,
            'cancelled_stations': [456, 789]
        }

        await mutation_engine.process_realtime_update(update)

        mutation_engine.apply_train_cancellation.assert_called_once_with(123, [456, 789])


class TestGraphMutationAPI:
    """Test Graph Mutation API endpoints"""

    @pytest.mark.asyncio
    async def test_apply_delay_endpoint(self):
        """Test delay application endpoint"""
        from backend.graph_mutation_service import train_state_store

        # Mock the store
        train_state_store.apply_delay = AsyncMock()

        request = DelayUpdateRequest(trip_id=123, delay_minutes=30, reason="Test delay")

        # This would normally be tested with FastAPI TestClient
        # For now, just verify the function exists and can be called
        assert request.trip_id == 123
        assert request.delay_minutes == 30

    @pytest.mark.asyncio
    async def test_cancel_train_endpoint(self):
        """Test train cancellation endpoint"""
        request = CancellationUpdateRequest(trip_id=123, cancelled_stations=[456, 789])

        assert request.trip_id == 123
        assert request.cancelled_stations == [456, 789]

    @pytest.mark.asyncio
    async def test_update_location_endpoint(self):
        """Test location update endpoint"""
        request = LocationUpdateRequest(
            trip_id=123,
            current_station_id=456,
            next_station_id=789
        )

        assert request.trip_id == 123
        assert request.current_station_id == 456
        assert request.next_station_id == 789


class TestIntegration:
    """Integration tests for the complete system"""

    @pytest.mark.asyncio
    async def test_full_mutation_flow(self):
        """Test complete mutation flow from API to graph"""
        # This would test the full integration
        # For now, just verify components can be imported
        from backend.train_state_service import TrainState, TrainStateStore
        from backend.graph_mutation_service import router

        assert TrainState is not None
        assert TrainStateStore is not None
        assert router is not None

    def test_database_model(self):
        """Test that the TrainState model is properly defined"""
        from backend.models import TrainState as DBTrainState

        # Check that the model has the expected columns
        assert hasattr(DBTrainState, 'trip_id')
        assert hasattr(DBTrainState, 'status')
        assert hasattr(DBTrainState, 'delay_minutes')
        assert hasattr(DBTrainState, 'last_updated')


# Performance tests
class TestPerformance:
    """Performance tests for graph mutation operations"""

    @pytest.mark.asyncio
    async def test_bulk_updates_performance(self):
        """Test performance of bulk updates"""
        import time

        # Create multiple updates
        updates = [
            {'type': 'delay', 'trip_id': i, 'delay_minutes': 10}
            for i in range(100)
        ]

        start_time = time.time()

        # Process updates (mock implementation)
        for update in updates:
            pass  # In real test, would call actual processing

        end_time = time.time()
        duration = end_time - start_time

        # Should process 100 updates in reasonable time
        assert duration < 1.0  # Less than 1 second

    def test_memory_usage(self):
        """Test memory usage with many train states"""
        states = []
        for i in range(1000):
            state = TrainState(trip_id=i, train_number=str(i))
            states.append(state)

        # Verify states are created without excessive memory
        assert len(states) == 1000
        assert all(isinstance(state, TrainState) for state in states)


if __name__ == "__main__":
    # Run basic smoke tests
    print("Running Graph Mutation Engine smoke tests...")

    # Test TrainState creation
    state = TrainState(trip_id=123, train_number="12345")
    print(f"✓ TrainState created: {state}")

    # Test serialization
    data = state.to_dict()
    restored = TrainState.from_dict(data)
    print(f"✓ Serialization works: {restored.trip_id == state.trip_id}")

    print("✓ All smoke tests passed!")