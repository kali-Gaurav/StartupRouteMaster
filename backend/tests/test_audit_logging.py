"""Tests for audit logging functionality."""

import pytest
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, Session, sessionmaker
from unittest.mock import Mock, patch, MagicMock

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from audit.audit_logger import (
    AuditLogger,
    set_request_context,
    get_request_context,
    initialize_audit_logging,
)

Base = declarative_base()


class TestModel(Base):
    """Test model for audit logging."""
    __tablename__ = "test_table"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    description = Column(Text, nullable=True)


class TestAuditContext:
    """Test request context management."""

    def test_set_and_get_context(self):
        """Test setting and retrieving request context."""
        context = {
            "user_id": "user123",
            "ip_address": "192.168.1.1",
            "session_id": "session456",
        }
        set_request_context(**context)
        retrieved = get_request_context()

        assert retrieved["user_id"] == "user123"
        assert retrieved["ip_address"] == "192.168.1.1"
        assert retrieved["session_id"] == "session456"

    def test_empty_context_by_default(self):
        """Test that context is empty by default."""
        # Create fresh context
        from audit.audit_logger import _request_context
        _request_context.set({})

        context = get_request_context()
        assert context == {}


class TestAuditLoggerUtilities:
    """Test AuditLogger utility methods."""

    def test_should_audit_table(self):
        """Test table audit filtering."""
        assert AuditLogger.should_audit_table("users") is True
        assert AuditLogger.should_audit_table("routes") is True
        assert AuditLogger.should_audit_table("audit_log") is False
        assert AuditLogger.should_audit_table("AUDIT_LOG") is False
        assert AuditLogger.should_audit_table("alembic_version") is False

    def test_get_record_values(self):
        """Test extracting values from mapped instance."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        # Create a test instance
        instance = TestModel(id=1, name="Test", description="A test record")
        session.add(instance)
        session.commit()

        # Get mapper
        from sqlalchemy import inspect as sa_inspect
        mapper = sa_inspect(TestModel)

        # Extract values
        values = AuditLogger.get_record_values(mapper, instance)

        assert values["id"] == 1
        assert values["name"] == "Test"
        assert values["description"] == "A test record"

        session.close()

    def test_create_audit_entry(self):
        """Test audit entry creation."""
        set_request_context(
            user_id="user1",
            ip_address="10.0.0.1",
            session_id="sess1"
        )

        entry = AuditLogger.create_audit_entry(
            table_name="users",
            operation="INSERT",
            record_id="user_123",
            after_values={"name": "Alice", "email": "alice@example.com"}
        )

        assert entry["table_name"] == "users"
        assert entry["operation"] == "INSERT"
        assert entry["record_id"] == "user_123"
        assert entry["user_id"] == "user1"
        assert entry["ip_address"] == "10.0.0.1"
        assert entry["session_id"] == "sess1"
        assert entry["after_values"]["name"] == "Alice"
        assert "timestamp" in entry


class TestAuditLoggingOperations:
    """Test audit logging for INSERT, UPDATE, DELETE."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory test database."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()

    def test_audit_insert(self, db_session):
        """Test INSERT operation tracking."""
        set_request_context(user_id="user1")

        # Mock audit write
        with patch.object(AuditLogger, "_write_audit_entry") as mock_write:
            instance = TestModel(id=1, name="Test")
            db_session.add(instance)
            db_session.flush()

            # Get mapper for manual testing
            from sqlalchemy import inspect as sa_inspect
            mapper = sa_inspect(TestModel)

            # Manually call log_insert (since event listeners may not fire in test)
            AuditLogger.log_insert(mapper, db_session.connection(), instance)

            # Verify audit entry was created
            assert mock_write.called
            call_args = mock_write.call_args
            entry = call_args[0][1]

            assert entry["operation"] == "INSERT"
            assert entry["table_name"] == "test_table"
            assert entry["user_id"] == "user1"

    def test_audit_delete(self, db_session):
        """Test DELETE operation tracking."""
        set_request_context(user_id="user2")

        instance = TestModel(id=1, name="ToDelete")
        db_session.add(instance)
        db_session.commit()

        with patch.object(AuditLogger, "_write_audit_entry") as mock_write:
            from sqlalchemy import inspect as sa_inspect
            mapper = sa_inspect(TestModel)

            AuditLogger.log_delete(mapper, db_session.connection(), instance)

            assert mock_write.called
            call_args = mock_write.call_args
            entry = call_args[0][1]

            assert entry["operation"] == "DELETE"
            assert entry["user_id"] == "user2"
            assert entry["before_values"]["name"] == "ToDelete"


class TestAuditQueryability:
    """Test querying the audit log."""

    def test_audit_entry_json_serializable(self):
        """Test that audit entries are JSON serializable."""
        entry = AuditLogger.create_audit_entry(
            table_name="users",
            operation="INSERT",
            record_id="1",
            after_values={"name": "Alice", "created_at": datetime(2026, 7, 30)}
        )

        # Should be JSON serializable
        json_str = json.dumps(entry, default=str)
        parsed = json.loads(json_str)

        assert parsed["table_name"] == "users"
        assert parsed["operation"] == "INSERT"

    def test_audit_log_schema_compatibility(self):
        """Test that audit entries match expected schema."""
        entry = AuditLogger.create_audit_entry(
            table_name="routes",
            operation="UPDATE",
            record_id="route_123",
            before_values={"status": "DRAFT"},
            after_values={"status": "PUBLISHED"}
        )

        # All required fields present
        required_fields = {
            "table_name", "operation", "record_id", "user_id", "timestamp",
            "ip_address", "session_id", "before_values", "after_values"
        }
        assert all(field in entry for field in required_fields)


class TestAuditExclusions:
    """Test that audit table itself is not audited."""

    def test_audit_table_excluded(self):
        """Test that audit_log table is excluded from auditing."""
        excluded = ["audit_log", "audit_logs", "alembic_version"]

        for table in excluded:
            assert not AuditLogger.should_audit_table(table)

    def test_normal_tables_included(self):
        """Test that normal tables are included."""
        tables = ["users", "routes", "bookings", "trips"]

        for table in tables:
            assert AuditLogger.should_audit_table(table)


class TestAuditPerformance:
    """Test audit logging performance characteristics."""

    def test_audit_entry_size(self):
        """Test that audit entries are reasonably sized."""
        entry = AuditLogger.create_audit_entry(
            table_name="users",
            operation="UPDATE",
            record_id="1",
            before_values={"name": "Old", "email": "old@example.com"},
            after_values={"name": "New", "email": "new@example.com"}
        )

        json_size = len(json.dumps(entry, default=str))

        # Audit entry should be < 10KB (reasonable limit)
        assert json_size < 10000

    def test_value_conversion(self):
        """Test that various data types are converted properly."""
        from datetime import datetime, date
        from uuid import UUID

        test_date = datetime(2026, 7, 30, 12, 0, 0)
        test_uuid = UUID("12345678-1234-5678-1234-567812345678")

        entry = AuditLogger.create_audit_entry(
            table_name="test",
            operation="INSERT",
            record_id="1",
            after_values={
                "string": "test",
                "int": 42,
                "float": 3.14,
                "bool": True,
                "null": None,
                "datetime": test_date,
                "uuid": test_uuid,
            }
        )

        # All values should be JSON serializable
        json_str = json.dumps(entry, default=str)
        assert "test" in json_str
        assert "42" in json_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
