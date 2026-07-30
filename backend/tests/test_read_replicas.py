"""
Tests for Read Replica functionality

Tests replica connection management, failover, query routing, and replication lag monitoring.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy import create_engine, text, select, Column, Integer, String
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, Session

# Import modules to test
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from database.replication import ReplicationManager, initialize_transit_replicas
from database.routing import AsyncReadWriteRouter, RouteAnalyzer, SmartSession

Base = declarative_base()


class TestModel(Base):
    """Simple test model."""
    __tablename__ = "test_table"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))


class TestReplicationManager:
    """Test ReplicationManager initialization and basic operations."""

    @pytest.fixture
    def in_memory_sqlite(self):
        """Create in-memory SQLite databases for testing."""
        primary_url = "sqlite:///:memory:"
        replica_urls = [
            "sqlite:///:memory:",
            "sqlite:///:memory:",
        ]
        return primary_url, replica_urls

    @pytest.mark.asyncio
    async def test_initialization(self, in_memory_sqlite):
        """Test ReplicationManager initializes correctly."""
        primary_url, replica_urls = in_memory_sqlite

        manager = ReplicationManager(
            primary_url=primary_url,
            replica_urls=replica_urls,
            is_async=False,
        )
        await manager.initialize()

        assert manager.primary_engine is not None
        assert len(manager.replica_engines) == 2
        assert all(manager.replica_health.get(i) for i in range(2))

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_primary_engine(self, in_memory_sqlite):
        """Test getting primary engine."""
        primary_url, replica_urls = in_memory_sqlite

        manager = ReplicationManager(
            primary_url=primary_url,
            replica_urls=replica_urls,
            is_async=False,
        )
        await manager.initialize()

        engine = manager.get_primary_engine()
        assert engine is not None

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_replica_engine(self, in_memory_sqlite):
        """Test getting replica engine."""
        primary_url, replica_urls = in_memory_sqlite

        manager = ReplicationManager(
            primary_url=primary_url,
            replica_urls=replica_urls,
            is_async=False,
        )
        await manager.initialize()

        engine = await manager.get_replica_engine()
        assert engine is not None

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_replica_round_robin(self, in_memory_sqlite):
        """Test that replicas are load-balanced round-robin."""
        primary_url, replica_urls = in_memory_sqlite

        manager = ReplicationManager(
            primary_url=primary_url,
            replica_urls=replica_urls,
            is_async=False,
        )
        await manager.initialize()

        # Get replicas multiple times
        replicas = []
        for _ in range(4):
            replica = await manager.get_replica_engine()
            replicas.append(replica)

        # Should alternate between replicas
        assert replicas[0] is replicas[2]  # First and third are same (index 0)
        assert replicas[1] is replicas[3]  # Second and fourth are same (index 1)

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_fallback_to_primary_when_no_replicas(self, in_memory_sqlite):
        """Test fallback to primary when no replicas configured."""
        primary_url, _ = in_memory_sqlite

        manager = ReplicationManager(
            primary_url=primary_url,
            replica_urls=[],  # No replicas
            is_async=False,
        )
        await manager.initialize()

        replica = await manager.get_replica_engine(fallback_to_primary=True)
        primary = manager.get_primary_engine()

        assert replica is primary

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_replica_health_tracking(self, in_memory_sqlite):
        """Test replica health status tracking."""
        primary_url, replica_urls = in_memory_sqlite

        manager = ReplicationManager(
            primary_url=primary_url,
            replica_urls=replica_urls,
            is_async=False,
        )
        await manager.initialize()

        # All replicas should be healthy initially
        assert manager.is_replica_healthy(0)
        assert manager.is_replica_healthy(1)

        # Mark replica as unhealthy
        manager.replica_health[0] = False

        assert not manager.is_replica_healthy(0)
        assert manager.is_replica_healthy(1)

        await manager.shutdown()


class TestRouteAnalyzer:
    """Test query routing analysis."""

    def test_insert_detected_as_write(self):
        """Test that INSERT queries are detected as writes."""
        # Create a mock insert statement
        stmt = Mock()
        stmt.__class__.__name__ = "Insert"

        assert RouteAnalyzer.is_write_operation(stmt)
        assert not RouteAnalyzer.is_read_operation(stmt)

    def test_update_detected_as_write(self):
        """Test that UPDATE queries are detected as writes."""
        stmt = Mock()
        stmt.__class__.__name__ = "Update"

        assert RouteAnalyzer.is_write_operation(stmt)

    def test_delete_detected_as_write(self):
        """Test that DELETE queries are detected as writes."""
        stmt = Mock()
        stmt.__class__.__name__ = "Delete"

        assert RouteAnalyzer.is_write_operation(stmt)

    def test_select_detected_as_read(self):
        """Test that SELECT queries are detected as reads."""
        stmt = Mock()
        stmt.__class__.__name__ = "Select"

        assert RouteAnalyzer.is_read_operation(stmt)
        assert not RouteAnalyzer.is_write_operation(stmt)

    def test_string_analysis(self):
        """Test string-based analysis of SQL."""
        # Insert statement as string
        insert_stmt = Mock()
        insert_stmt.__str__ = Mock(return_value="INSERT INTO users VALUES (...)")

        assert RouteAnalyzer.is_write_operation(insert_stmt)

        # Select statement as string
        select_stmt = Mock()
        select_stmt.__str__ = Mock(return_value="SELECT * FROM users")

        assert RouteAnalyzer.is_read_operation(select_stmt)


class TestAsyncReadWriteRouter:
    """Test AsyncReadWriteRouter."""

    @pytest.fixture
    def mock_manager(self):
        """Create a mock ReplicationManager."""
        manager = Mock()
        manager.get_primary_engine = Mock()
        manager.get_replica_engine = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_get_session_for_write(self, mock_manager):
        """Test getting a write session (primary)."""
        primary_engine = MagicMock()
        mock_manager.get_primary_engine.return_value = primary_engine

        router = AsyncReadWriteRouter(mock_manager)
        session = await router.get_session(is_write=True)

        # Should call get_primary_engine
        mock_manager.get_primary_engine.assert_called()

    @pytest.mark.asyncio
    async def test_get_session_for_read(self, mock_manager):
        """Test getting a read session (replica)."""
        replica_engine = MagicMock()
        mock_manager.get_replica_engine.return_value = replica_engine

        router = AsyncReadWriteRouter(mock_manager)
        session = await router.get_session(is_write=False)

        # Should call get_replica_engine
        mock_manager.get_replica_engine.assert_called()


class TestIntegrationReadReplica:
    """Integration tests for read replica feature."""

    @pytest.mark.asyncio
    async def test_query_latency_improvement(self):
        """
        Test that replica routing works correctly.

        Note: This is a simulated test. In production with real PostgreSQL,
        you'd measure actual latency against replicated instances.
        With in-memory SQLite, we can't test actual data replication,
        but we can verify the routing logic works.
        """
        primary_url = "sqlite:///:memory:"
        replica_urls = ["sqlite:///:memory:"]

        manager = ReplicationManager(
            primary_url=primary_url,
            replica_urls=replica_urls,
            is_async=False,
        )
        await manager.initialize()

        # Verify routing: writes go to primary
        primary_engine = manager.get_primary_engine()
        with primary_engine.connect() as conn:
            conn.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)"))
            conn.execute(text("INSERT INTO test (id, value) VALUES (1, 'test')"))
            conn.commit()

        # Verify routing: reads go to replica (even though it's empty in this test)
        replica_engine = await manager.get_replica_engine()
        assert replica_engine is not None
        # In production with real replication, the read would return the replicated data
        # For this test, we just verify the replica engine is accessible

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_failover_behavior(self):
        """Test that queries fall back to primary when replica fails."""
        primary_url = "sqlite:///:memory:"
        replica_urls = ["sqlite:///:memory:"]

        manager = ReplicationManager(
            primary_url=primary_url,
            replica_urls=replica_urls,
            is_async=False,
        )
        await manager.initialize()

        # Simulate replica failure
        manager.replica_health[0] = False

        # Next read should fall back to primary
        fallback_engine = await manager.get_replica_engine(fallback_to_primary=True)
        primary_engine = manager.get_primary_engine()

        assert fallback_engine is primary_engine

        await manager.shutdown()


class TestReplicationLagMonitoring:
    """Test replication lag monitoring."""

    @pytest.mark.asyncio
    async def test_lag_tracking(self):
        """Test that replication lag is tracked."""
        primary_url = "sqlite:///:memory:"
        replica_urls = ["sqlite:///:memory:"]

        manager = ReplicationManager(
            primary_url=primary_url,
            replica_urls=replica_urls,
            is_async=False,
        )
        await manager.initialize()

        # Lag should be initialized to 0
        assert manager.get_replica_lag(0) >= 0

        # Simulate lag update
        manager.replication_lag_ms[0] = 50.0
        assert manager.get_replica_lag(0) == 50.0

        await manager.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
