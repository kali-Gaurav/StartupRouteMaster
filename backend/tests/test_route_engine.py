import pytest
from backend.utils.time_utils import (
    time_string_to_minutes,
    minutes_to_time_string,
    calculate_duration,
    format_duration,
    get_day_of_week,
    is_operating_on_day,
)
from backend.utils.graph_utils import haversine_distance
from backend.utils.validators import (
    validate_date,
    validate_phone,
    validate_budget,
    validate_operating_days,
)
from backend.config import Config


class TestTimeUtils:
    """Test time utility functions."""

    def test_time_string_to_minutes(self):
        assert time_string_to_minutes("00:00") == 0
        assert time_string_to_minutes("12:30") == 750
        assert time_string_to_minutes("23:59") == 1439

    def test_time_string_to_minutes_invalid(self):
        with pytest.raises(ValueError):
            time_string_to_minutes("25:00")

    def test_minutes_to_time_string(self):
        assert minutes_to_time_string(0) == "00:00"
        assert minutes_to_time_string(750) == "12:30"
        assert minutes_to_time_string(1439) == "23:59"

    def test_calculate_duration_same_day(self):
        duration = calculate_duration("10:00", "12:30")
        assert duration == 150

    def test_calculate_duration_next_day(self):
        duration = calculate_duration("22:00", "06:00")
        assert duration == 480

    def test_format_duration(self):
        assert format_duration(60) == "1h"
        assert format_duration(30) == "30m"
        assert format_duration(90) == "1h 30m"

    def test_get_day_of_week(self):
        day = get_day_of_week("2025-01-06")
        assert day == 0

    def test_is_operating_on_day(self):
        assert is_operating_on_day("1111111", "2025-01-06") is True
        assert is_operating_on_day("0000000", "2025-01-06") is False
        assert is_operating_on_day("1000000", "2025-01-06") is True


class TestGraphUtils:
    """Test graph utility functions (keeps haversine test)."""

    def test_haversine_distance(self):
        distance = haversine_distance(
            lat1=19.0760,
            lon1=72.8777,
            lat2=15.2993,
            lon2=73.8243,
        )
        assert 400 < distance < 450


class TestValidators:
    """Test validation functions."""

    def test_validate_date_future(self):
        from datetime import datetime, timedelta

        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert validate_date(future_date) is True

    def test_validate_date_past(self):
        from datetime import datetime, timedelta

        past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert validate_date(past_date) is False

    def test_validate_date_invalid_format(self):
        assert validate_date("2025/01/01") is False

    def test_validate_phone_valid(self):
        assert validate_phone("9876543210") is True

    def test_validate_phone_invalid(self):
        assert validate_phone("123") is False
        assert validate_phone("abcdefghij") is False

    def test_validate_budget_valid(self):
        assert validate_budget("economy") is True
        assert validate_budget("standard") is True
        assert validate_budget("premium") is True
        assert validate_budget("all") is True

    def test_validate_budget_invalid(self):
        assert validate_budget("luxury") is False

    def test_validate_operating_days_valid(self):
        assert validate_operating_days("1111111") is True
        assert validate_operating_days("1010101") is True

    def test_validate_operating_days_invalid(self):
        assert validate_operating_days("11111") is False
        assert validate_operating_days("12345678") is False
        assert validate_operating_days("abcdefg") is False


class TestRouteEngine:
    """Unit tests for the RAPTOR MVP implementation in RouteEngine."""

    def setup_routeengine(self):
        from backend.services.route_engine import route_engine
        # reset internal maps
        route_engine.stations_map = {}
        route_engine.segments_map = {}
        route_engine.route_segments = {}
        route_engine.station_name_to_id = {}
        route_engine._is_loaded = True
        return route_engine

    def test_direct_route(self):
        re = self.setup_routeengine()
        # stations
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}}
        re.station_name_to_id = {"a": "S1", "b": "S2"}
        # direct segment S1 -> S2
        seg = {"id": "seg1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "10:00", "duration": 120, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        re.segments_map = {"seg1": seg}
        re.route_segments = {"route_v1": [seg]}

        results = re.search_routes("A", "B", "2026-02-16")
        assert len(results) >= 1
        r = results[0]
        assert r["num_transfers"] == 0
        assert r["total_cost"] == 100.0
        assert len(r["segments"]) == 1

    def test_one_transfer(self):
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}, "S3": {"name": "C"}}
        re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3"}

        s1 = {"id": "seg1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 50.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        s2 = {"id": "seg2", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 60.0, "operating_days": "1111111", "vehicle_id": "v2", "mode": "train"}

        re.segments_map = {"seg1": s1, "seg2": s2}
        re.route_segments = {"route_v1": [s1], "route_v2": [s2]}

        results = re.search_routes("A", "C", "2026-02-16")
        assert len(results) >= 1
        r = results[0]
        assert r["num_transfers"] == 1
        assert r["total_cost"] == pytest.approx(110.0)
        assert len(r["segments"]) == 2

    def test_two_transfers(self):
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}, "S3": {"name": "C"}, "S4": {"name": "D"}}
        re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3", "d": "S4"}

        s1 = {"id": "seg1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 30.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        s2 = {"id": "seg2", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 35.0, "operating_days": "1111111", "vehicle_id": "v2", "mode": "train"}
        s3 = {"id": "seg3", "source_station_id": "S3", "dest_station_id": "S4", "departure": "11:00", "arrival": "12:00", "duration": 60, "cost": 40.0, "operating_days": "1111111", "vehicle_id": "v3", "mode": "train"}

        re.segments_map = {"seg1": s1, "seg2": s2, "seg3": s3}
        re.route_segments = {"route_v1": [s1], "route_v2": [s2], "route_v3": [s3]}

        results = re.search_routes("A", "D", "2026-02-16")
        assert len(results) >= 1
        r = results[0]
        assert r["num_transfers"] == 2
        assert r["total_cost"] == pytest.approx(105.0)
        assert len(r["segments"]) == 3

    def test_transfer_window_enforced(self):
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}, "S3": {"name": "C"}}
        re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3"}

        # s1 arrives at 09:00, s2 departs at 09:05 -> wait 5m
        s1 = {"id": "seg1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 30.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        s2 = {"id": "seg2", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:05", "arrival": "10:00", "duration": 55, "cost": 40.0, "operating_days": "1111111", "vehicle_id": "v2", "mode": "train"}

        re.segments_map = {"seg1": s1, "seg2": s2}
        re.route_segments = {"route_v1": [s1], "route_v2": [s2]}

        # Temporarily increase min transfer to 10 minutes
        old_min = Config.TRANSFER_WINDOW_MIN
        Config.TRANSFER_WINDOW_MIN = 10
        try:
            results = re.search_routes("A", "C", "2026-02-16")
            assert results == []
        finally:
            Config.TRANSFER_WINDOW_MIN = old_min

    def test_overnight_day_offset(self):
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}}
        re.station_name_to_id = {"a": "S1", "b": "S2"}

        # dep 23:30 arr 01:30 (next day)
        seg = {"id": "seg_overnight", "source_station_id": "S1", "dest_station_id": "S2", "departure": "23:30", "arrival": "01:30", "duration": 120, "cost": 80.0, "operating_days": "1111111", "vehicle_id": "v_overnight", "arrival_day_offset": 1, "mode": "train"}
        re.segments_map = {"seg_overnight": seg}
        re.route_segments = {"route_v_overnight": [seg]}

        results = re.search_routes("A", "B", "2026-02-16")
        assert len(results) >= 1
        r = results[0]
        assert r["total_duration_minutes"] == 120

    def test_operating_days_respected(self):
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}}
        re.station_name_to_id = {"a": "S1", "b": "S2"}

        # operates only on Monday (weekday index 0)
        seg = {"id": "seg_mononly", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 30.0, "operating_days": "1000000", "vehicle_id": "v_mon", "mode": "train"}
        re.segments_map = {"seg_mononly": seg}
        re.route_segments = {"route_v_mon": [seg]}

        monday = "2026-02-16"  # Monday
        tuesday = "2026-02-17" # Tuesday
        assert len(re.search_routes("A", "B", monday)) >= 1
        assert re.search_routes("A", "B", tuesday) == []

    def test_build_route_indices_and_search_with_indices(self):
        """Verify per-route indices are built and search still returns correct routes."""
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}, "S3": {"name": "C"}}
        re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3"}

        # route with two sequential segments
        s1 = {"id": "seg1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 50.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        s2 = {"id": "seg2", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 60.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}

        re.segments_map = {"seg1": s1, "seg2": s2}
        re.route_segments = {"route_v1": [s1, s2]}

        # build indices and assert structure
        re._build_route_indices()
        assert "route_v1" in re.route_stop_index
        assert re.route_stop_index["route_v1"]["S1"] == [0]
        assert re.route_stop_departures["route_v1"]["S1"] == [480]

        # search must still succeed (index-aware path)
        results = re.search_routes("A", "C", "2026-02-16")
        assert len(results) >= 1
        r = results[0]
        assert r["num_transfers"] == 1
        assert r["total_cost"] == pytest.approx(110.0)

    def test_cache_invalidation_on_schema_mismatch(self, tmp_path):
        import pickle
        import importlib
        from backend.services import route_engine as re_mod

        # create a bogus cache file with wrong schema_version
        bogus = {"meta": {"schema_version": 999, "etl_timestamp": "now"}, "state": {}}
        cache_file = tmp_path / "route_engine_graph.pkl"
        with open(cache_file, "wb") as f:
            pickle.dump(bogus, f)

        # monkeypatch module-level GRAPH_CACHE_FILE
        import backend.services.route_engine as re_mod2
        re_mod2.GRAPH_CACHE_FILE = str(cache_file)

        re = re_mod2.route_engine
        re._is_loaded = False
        assert re._load_graph_state() is False
        # cleanup
        cache_file.unlink()

