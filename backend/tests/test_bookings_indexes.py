"""
Unit tests for bookings table indexes.
Tests verify that the migration file for indexes exists and is correctly configured.
"""
import pytest
import os
from pathlib import Path


class TestBookingsIndexesMigration:
    """Test cases for bookings table indexes migration file."""

    def test_migration_file_exists(self):
        """Test that the migration file for bookings indexes exists."""
        migrations_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_file = migrations_dir / "abc123def459_add_bookings_table_indexes.py"
        
        assert migration_file.exists(), \
            f"Migration file {migration_file.name} should exist in alembic/versions/"

    def test_migration_has_composite_index(self):
        """Test that migration creates composite index on (user_id, travel_date)."""
        migrations_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_file = migrations_dir / "abc123def459_add_bookings_table_indexes.py"
        
        assert migration_file.exists(), "Migration file must exist"
        
        content = migration_file.read_text()
        
        # Check for composite index creation
        assert "idx_bookings_user_travel_date" in content, \
            "Migration should create idx_bookings_user_travel_date index"
        assert "user_id" in content and "travel_date" in content, \
            "Composite index should include user_id and travel_date columns"

    def test_migration_has_status_index(self):
        """Test that migration creates index on booking_status."""
        migrations_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_file = migrations_dir / "abc123def459_add_bookings_table_indexes.py"
        
        assert migration_file.exists(), "Migration file must exist"
        
        content = migration_file.read_text()
        
        # Check for status index creation
        assert "idx_bookings_status" in content, \
            "Migration should create idx_bookings_status index"
        assert "booking_status" in content, \
            "Status index should include booking_status column"

    def test_migration_has_downgrade(self):
        """Test that migration has proper downgrade logic."""
        migrations_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_file = migrations_dir / "abc123def459_add_bookings_table_indexes.py"
        
        assert migration_file.exists(), "Migration file must exist"
        
        content = migration_file.read_text()
        
        # Check for downgrade function
        assert "def downgrade" in content, \
            "Migration should have a downgrade function"
        assert "DROP INDEX IF EXISTS" in content, \
            "Downgrade should drop the indexes"

    def test_migration_revisions_are_correct(self):
        """Test that migration has correct revision identifiers."""
        migrations_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_file = migrations_dir / "abc123def459_add_bookings_table_indexes.py"
        
        assert migration_file.exists(), "Migration file must exist"
        
        content = migration_file.read_text()
        
        # Check revision ID
        assert "revision: str = 'abc123def459'" in content, \
            "Migration should have correct revision ID"
        
        # Check down_revision points to the latest migration
        assert "down_revision: Union[str, Sequence[str], None] = 'ff2a3b4c5d6'" in content, \
            "Migration should depend on ff2a3b4c5d6 (latest migration)"


class TestBookingsIndexNaming:
    """Test cases for index naming conventions in the migration."""

    def test_index_names_follow_convention(self):
        """Test that index names follow the project naming convention."""
        migrations_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_file = migrations_dir / "abc123def459_add_bookings_table_indexes.py"
        
        assert migration_file.exists(), "Migration file must exist"
        
        content = migration_file.read_text()
        
        # Index names should start with idx_
        assert "idx_bookings_user_travel_date" in content, \
            "Index name should start with 'idx_'"
        assert "idx_bookings_status" in content, \
            "Index name should start with 'idx_'"

    def test_uses_if_not_exists(self):
        """Test that indexes are created with IF NOT EXISTS clause."""
        migrations_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_file = migrations_dir / "abc123def459_add_bookings_table_indexes.py"
        
        assert migration_file.exists(), "Migration file must exist"
        
        content = migration_file.read_text()
        
        # Should use IF NOT EXISTS to be idempotent
        assert "IF NOT EXISTS" in content, \
            "Index creation should use IF NOT EXISTS clause for idempotency"


class TestBookingsIndexCoverage:
    """Test cases for verifying index coverage for common query patterns."""

    def test_supports_user_booking_history_query(self):
        """Test that composite index supports user booking history queries."""
        migrations_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_file = migrations_dir / "abc123def459_add_bookings_table_indexes.py"
        
        assert migration_file.exists(), "Migration file must exist"
        
        content = migration_file.read_text()
        
        # The composite index (user_id, travel_date) supports:
        # SELECT * FROM bookings WHERE user_id = ? ORDER BY travel_date
        # SELECT * FROM bookings WHERE user_id = ? AND travel_date BETWEEN ? AND ?
        assert "user_id" in content and "travel_date" in content, \
            "Composite index should support user booking history queries"

    def test_supports_status_filter_query(self):
        """Test that status index supports filtering by booking status."""
        migrations_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_file = migrations_dir / "abc123def459_add_bookings_table_indexes.py"
        
        assert migration_file.exists(), "Migration file must exist"
        
        content = migration_file.read_text()
        
        # The status index supports:
        # SELECT * FROM bookings WHERE booking_status = ?
        # SELECT * FROM bookings WHERE booking_status IN (?, ?)
        assert "booking_status" in content, \
            "Status index should support filtering by booking status"
