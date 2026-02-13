"""Tests for ETL pipeline."""

import pytest
import os
import sqlite3
from pathlib import Path
from datetime import datetime

from backend.etl.sqlite_to_postgres import (
    SQLiteReader,
    PostgresLoader,
    OperatingDaysBitmask,
    calculate_duration,
    run_etl
)


class TestOperatingDaysBitmask:
    """Test bitmask generation."""

    def test_all_days(self):
        mask = OperatingDaysBitmask.create(True, True, True, True, True, True, True)
        assert mask == "1111111"

    def test_weekdays_only(self):
        mask = OperatingDaysBitmask.create(True, True, True, True, True, False, False)
        assert mask == "1111100"

    def test_no_days(self):
        mask = OperatingDaysBitmask.create()
        assert mask == "0000000"


class TestDurationCalculation:
    """Test duration calculation."""

    def test_same_day(self):
        duration = calculate_duration("08:00", "20:00")
        assert duration == 12 * 60  # 720 minutes

    def test_overnight(self):
        duration = calculate_duration("22:00", "06:00")
        assert duration == 8 * 60  # 480 minutes

    def test_zero_duration(self):
        duration = calculate_duration("08:00", "08:00")
        assert duration == 0


class TestSQLiteReader:
    """Test reading from SQLite."""

    def test_read_stations_master(self):
        """Test reading stations (requires railway_manager.db)."""
        db_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "railway_manager.db"
        )

        if not os.path.exists(db_path):
            pytest.skip(f"railway_manager.db not found at {db_path}")

        reader = SQLiteReader(db_path)
        stations = reader.read_stations_master()

        assert len(stations) > 0
        assert all('station_code' in s for s in stations)
        assert all('station_name' in s for s in stations)


class TestETLPipeline:
    """Integration test (requires real databases)."""

    def test_etl_runs_without_error(self):
        """Test full ETL pipeline."""
        db_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "railway_manager.db"
        )

        if not os.path.exists(db_path):
            pytest.skip("railway_manager.db not found")

        results = run_etl(db_path)

        assert results['stations_synced'] > 0
        assert results['segments_created'] > 0
        assert results['errors'] == 0