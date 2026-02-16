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

    async def test_direct_route(self):
        re = self.setup_routeengine()
        # stations
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}}
        re.station_name_to_id = {"a": "S1", "b": "S2"}
        # direct segment S1 -> S2
        seg = {"id": "seg1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "10:00", "duration": 120, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        re.segments_map = {"seg1": seg}
        re.route_segments = {"route_v1": [seg]}

        results = await re.search_routes("A", "B", "2026-02-16")
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


class TestParetoPruning:
    """Test Pareto-optimal route filtering."""

    def setup_routeengine(self):
        from backend.services.route_engine import route_engine
        # reset internal maps
        route_engine.stations_map = {}
        route_engine.segments_map = {}
        route_engine.route_segments = {}
        route_engine.station_name_to_id = {}
        route_engine._is_loaded = True
        return route_engine

    def test_pareto_pruning_multiple_options(self):
        """Test that only Pareto-optimal routes are returned when multiple paths exist."""
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}, "S3": {"name": "C"}}
        re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3"}

        # Create three routes with different time/cost trade-offs:
        # Route 1: Fast but expensive (direct, 2h, $100) - Pareto optimal
        # Route 2: Slow and expensive (via transfer, 4h, $150) - dominated
        # Route 3: Slow but cheap (via transfer, 4h, $80) - Pareto optimal
        # Route 4: Medium time/medium cost (via transfer, 3h, $120) - dominated by Route 1 and Route 3

        # Direct route: A -> C (fast, expensive)
        seg_direct = {
            "id": "seg_direct",
            "source_station_id": "S1",
            "dest_station_id": "S3",
            "departure": "08:00",
            "arrival": "10:00",
            "duration": 120,
            "cost": 100.0,
            "operating_days": "1111111",
            "vehicle_id": "v_direct",
            "mode": "train"
        }

        # Transfer route 1: A -> B -> C (slow, expensive) - dominated
        seg_ab_slow = {
            "id": "seg_ab_slow",
            "source_station_id": "S1",
            "dest_station_id": "S2",
            "departure": "08:00",
            "arrival": "10:00",
            "duration": 120,
            "cost": 75.0,
            "operating_days": "1111111",
            "vehicle_id": "v_slow",
            "mode": "train"
        }
        seg_bc_slow = {
            "id": "seg_bc_slow",
            "source_station_id": "S2",
            "dest_station_id": "S3",
            "departure": "10:30",
            "arrival": "12:30",
            "duration": 120,
            "cost": 75.0,
            "operating_days": "1111111",
            "vehicle_id": "v_slow",
            "mode": "train"
        }

        # Transfer route 2: A -> B -> C (slow, cheap) - Pareto optimal
        seg_ab_cheap = {
            "id": "seg_ab_cheap",
            "source_station_id": "S1",
            "dest_station_id": "S2",
            "departure": "08:00",
            "arrival": "10:00",
            "duration": 120,
            "cost": 40.0,
            "operating_days": "1111111",
            "vehicle_id": "v_cheap",
            "mode": "train"
        }
        seg_bc_cheap = {
            "id": "seg_bc_cheap",
            "source_station_id": "S2",
            "dest_station_id": "S3",
            "departure": "10:30",
            "arrival": "12:30",
            "duration": 120,
            "cost": 40.0,
            "operating_days": "1111111",
            "vehicle_id": "v_cheap",
            "mode": "train"
        }

        # Transfer route 3: A -> B -> C (medium time, medium cost) - dominated
        seg_ab_med = {
            "id": "seg_ab_med",
            "source_station_id": "S1",
            "dest_station_id": "S2",
            "departure": "08:00",
            "arrival": "09:30",
            "duration": 90,
            "cost": 60.0,
            "operating_days": "1111111",
            "vehicle_id": "v_med",
            "mode": "train"
        }
        seg_bc_med = {
            "id": "seg_bc_med",
            "source_station_id": "S2",
            "dest_station_id": "S3",
            "departure": "10:00",
            "arrival": "11:30",
            "duration": 90,
            "cost": 60.0,
            "operating_days": "1111111",
            "vehicle_id": "v_med",
            "mode": "train"
        }

        re.segments_map = {
            "seg_direct": seg_direct,
            "seg_ab_slow": seg_ab_slow,
            "seg_bc_slow": seg_bc_slow,
            "seg_ab_cheap": seg_ab_cheap,
            "seg_bc_cheap": seg_bc_cheap,
            "seg_ab_med": seg_ab_med,
            "seg_bc_med": seg_bc_med
        }
        re.route_segments = {
            "route_direct": [seg_direct],
            "route_slow": [seg_ab_slow, seg_bc_slow],
            "route_cheap": [seg_ab_cheap, seg_bc_cheap],
            "route_med": [seg_ab_med, seg_bc_med]
        }

        # Temporarily set PARETO_LIMIT to high value to see all Pareto-optimal
        from backend.config import Config
        old_limit = Config.PARETO_LIMIT
        Config.PARETO_LIMIT = 10
        try:
            results = re.search_routes("A", "C", "2026-02-16")

            # Should return exactly 2 Pareto-optimal routes:
            # 1. Direct route: 2h, $100 (fastest)
            # 2. Cheap transfer route: 4h, $80 (cheapest)
            # The slow expensive (4h, $150) and medium (3h, $120) should be dominated
            assert len(results) == 2

            # Sort by total cost for consistent checking
            results.sort(key=lambda x: x["total_cost"])

            # First result should be the cheap transfer route
            cheap_route = results[0]
            assert cheap_route["total_cost"] == pytest.approx(80.0)
            assert cheap_route["total_duration_minutes"] == 240  # 4 hours
            assert len(cheap_route["segments"]) == 2

            # Second result should be the direct route
            direct_route = results[1]
            assert direct_route["total_cost"] == pytest.approx(100.0)
            assert direct_route["total_duration_minutes"] == 120  # 2 hours
            assert len(direct_route["segments"]) == 1

        finally:
            Config.PARETO_LIMIT = old_limit

    def test_pareto_limit_enforced(self):
        """Test that PARETO_LIMIT is respected when more optimal routes exist."""
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}}
        re.station_name_to_id = {"a": "S1", "b": "S2"}

        # Create many direct routes with slightly different costs/times
        # All should be Pareto-optimal since they trade off time vs cost
        segments = []
        for i in range(10):
            seg = {
                "id": f"seg_{i}",
                "source_station_id": "S1",
                "dest_station_id": "S2",
                "departure": f"{8+i:02d}:00",
                "arrival": f"{9+i:02d}:00",
                "duration": 60,
                "cost": 50.0 + i * 5.0,  # Increasing cost
                "operating_days": "1111111",
                "vehicle_id": f"v_{i}",
                "mode": "train"
            }
            segments.append(seg)
            re.segments_map[seg["id"]] = seg
            re.route_segments[f"route_v_{i}"] = [seg]

        from backend.config import Config
        old_limit = Config.PARETO_LIMIT
        Config.PARETO_LIMIT = 3  # Limit to 3 results
        try:
            results = re.search_routes("A", "B", "2026-02-16")
            # Should return at most PARETO_LIMIT results
            assert len(results) <= 3
            # All returned routes should be Pareto-optimal (no dominated ones)
            for i, route in enumerate(results):
                for other_route in results[i+1:]:
                    # No route should dominate another
                    assert not (route["total_duration_minutes"] <= other_route["total_duration_minutes"] and
                              route["total_cost"] <= other_route["total_cost"] and
                              (route["total_duration_minutes"] < other_route["total_duration_minutes"] or
                               route["total_cost"] < other_route["total_cost"]))
        finally:
            Config.PARETO_LIMIT = old_limit


class TestFeasibilityScoring:
    """Tests for feasibility scoring, safety and night-layover penalties."""

    def setup_routeengine(self):
        from backend.services.route_engine import route_engine
        route_engine.stations_map = {}
        route_engine.segments_map = {}
        route_engine.route_segments = {}
        route_engine.station_name_to_id = {}
        route_engine._is_loaded = True
        return route_engine

    def test_safer_layover_preferred(self):
        re = self.setup_routeengine()
        # stations A, B (unsafe), D (safe), C
        re.stations_map = {
            "S1": {"name": "A", "safety_score": 80},
            "S2": {"name": "B", "safety_score": 10},
            "S3": {"name": "C", "safety_score": 80},
            "S4": {"name": "D", "safety_score": 90}
        }
        re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3", "d": "S4"}

        # Two transfer routes with a clear trade-off so both are Pareto-optimal:
        # - via B: faster but more expensive (unsafe)
        # - via D: slower but cheaper (safe)
        s1 = {"id": "seg_ab", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:40", "duration": 100, "cost": 70.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        s2 = {"id": "seg_bc", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:50", "arrival": "10:40", "duration": 50, "cost": 50.0, "operating_days": "1111111", "vehicle_id": "v2", "mode": "train"}

        s3 = {"id": "seg_ad", "source_station_id": "S1", "dest_station_id": "S4", "departure": "08:00", "arrival": "09:30", "duration": 90, "cost": 40.0, "operating_days": "1111111", "vehicle_id": "v3", "mode": "train"}
        s4 = {"id": "seg_dc", "source_station_id": "S4", "dest_station_id": "S3", "departure": "09:45", "arrival": "11:00", "duration": 75, "cost": 60.0, "operating_days": "1111111", "vehicle_id": "v4", "mode": "train"}

        re.segments_map = {"seg_ab": s1, "seg_bc": s2, "seg_ad": s3, "seg_dc": s4}
        re.route_segments = {"route_1": [s1, s2], "route_2": [s3, s4]}

        results = re.search_routes("A", "C", "2026-02-16")
        assert len(results) >= 2
        # The route via D (safe layover) should have higher feasibility_score than via B (unsafe)
        scores = {tuple(seg['from'] for seg in r['segments']): r['feasibility_score'] for r in results}
        route_via_b = scores.get(("A", "B"))
        route_via_d = scores.get(("A", "D"))
        assert route_via_d is not None and route_via_b is not None
        assert route_via_d > route_via_b

    def test_night_layover_penalized(self):
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A", "safety_score": 60}, "S2": {"name": "B", "safety_score": 60}, "S3": {"name": "C", "safety_score": 60}}
        re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3"}

        # Route 1: day layover at B (slightly slower)
        s1 = {"id": "s1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:30", "duration": 90, "cost": 50.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        s2 = {"id": "s2", "source_station_id": "S2", "dest_station_id": "S3", "departure": "10:00", "arrival": "11:00", "duration": 60, "cost": 50.0, "operating_days": "1111111", "vehicle_id": "v2", "mode": "train"}

        # Route 2: night layover at B (slightly faster but gets a night-penalty)
        s3 = {"id": "s3", "source_station_id": "S1", "dest_station_id": "S2", "departure": "22:30", "arrival": "23:30", "duration": 60, "cost": 40.0, "operating_days": "1111111", "vehicle_id": "v3", "mode": "train"}
        s4 = {"id": "s4", "source_station_id": "S2", "dest_station_id": "S3", "departure": "00:30", "arrival": "01:30", "duration": 60, "cost": 50.0, "operating_days": "1111111", "vehicle_id": "v4", "mode": "train", "departure_day_offset": 1}

        re.segments_map = {"s1": s1, "s2": s2, "s3": s3, "s4": s4}
        re.route_segments = {"route_day": [s1, s2], "route_night": [s3, s4]}

        results = re.search_routes("A", "C", "2026-02-16")
        assert len(results) >= 2
        # find feasibility scores
        scores = [r['feasibility_score'] for r in results]
        # night route must have strictly lower feasibility score due to night-layover penalty
        night_scores = [r['feasibility_score'] for r in results if any(seg['departure_time']=="22:30" or seg['arrival_time']=="23:30" for seg in r['segments'])]
        day_scores = [r['feasibility_score'] for r in results if any(seg['departure_time']=="08:00" for seg in r['segments'])]
        assert night_scores and day_scores
        assert max(day_scores) > max(night_scores)


class TestReliabilityAwareRouting:
    """Test reliability-aware deterministic ranking (Phase-6)"""

    def setup_routeengine(self):
        from backend.services.route_engine import RouteEngine
        route_engine = RouteEngine()
        route_engine.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}, "S3": {"name": "C"}}
        route_engine.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3"}
        route_engine.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3"}
        route_engine.routes_by_station = {"S1": ["route_1", "route_2"], "S2": ["route_1", "route_2"], "S3": ["route_1", "route_2"]}
        route_engine.route_stop_index = {"route_1": {"S1": [0], "S2": [1], "S3": [2]}, "route_2": {"S1": [0], "S2": [1], "S3": [2]}}
        route_engine.route_stop_departures = {"route_1": {"S1": ["08:00"], "S2": ["09:00"]}, "route_2": {"S1": ["08:00"], "S2": ["09:00"]}}
        route_engine._is_loaded = True
        return route_engine

    def test_reliability_weight_zero_no_change(self, monkeypatch):
        """When ROUTE_RELIABILITY_WEIGHT=0, ranking should be identical to baseline"""
        from backend.config import Config
        monkeypatch.setattr(Config, 'ROUTE_RELIABILITY_WEIGHT', 0.0)

        re = self.setup_routeengine()
        # Two routes: one with high-reliability train, one with low-reliability
        s1 = {"id": "seg_ab1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "reliable_train", "mode": "train"}
        s2 = {"id": "seg_bc1", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "reliable_train", "mode": "train"}

        s3 = {"id": "seg_ab2", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "unreliable_train", "mode": "train"}
        s4 = {"id": "seg_bc2", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "unreliable_train", "mode": "train"}

        re.segments_map = {"seg_ab1": s1, "seg_bc1": s2, "seg_ab2": s3, "seg_bc2": s4}
        re.route_segments = {"route_reliable": [s1, s2], "route_unreliable": [s3, s4]}

        # Mock reliability service to return different scores
        async def mock_get_train_reliabilities(train_ids):
            return {"reliable_train": 0.9, "unreliable_train": 0.3}

        monkeypatch.setattr("backend.services.route_engine.get_train_reliabilities", mock_get_train_reliabilities)

        results = re.search_routes("A", "C", "2026-02-16")
        assert len(results) >= 2

        # Extract feasibility scores
        scores = {r['id']: r['feasibility_score'] for r in results}

        # With weight=0, both routes should have identical scores (no reliability penalty)
        assert abs(scores.get('route_reliable', 0) - scores.get('route_unreliable', 0)) < 1e-6

    def test_reliability_weight_positive_prefers_stable(self, monkeypatch):
        """When ROUTE_RELIABILITY_WEIGHT > 0, stable routes should be preferred"""
        from backend.config import Config
        monkeypatch.setattr(Config, 'ROUTE_RELIABILITY_WEIGHT', 0.25)

        re = self.setup_routeengine()
        # Two identical routes except for train reliability
        s1 = {"id": "seg_ab1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "reliable_train", "mode": "train"}
        s2 = {"id": "seg_bc1", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "reliable_train", "mode": "train"}

        s3 = {"id": "seg_ab2", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "unreliable_train", "mode": "train"}
        s4 = {"id": "seg_bc2", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "unreliable_train", "mode": "train"}

        re.segments_map = {"seg_ab1": s1, "seg_bc1": s2, "seg_ab2": s3, "seg_bc2": s4}
        re.route_segments = {"route_reliable": [s1, s2], "route_unreliable": [s3, s4]}

        # Mock reliability service
        async def mock_get_train_reliabilities(train_ids):
            return {"reliable_train": 0.9, "unreliable_train": 0.3}

        monkeypatch.setattr("backend.services.route_engine.get_train_reliabilities", mock_get_train_reliabilities)

        results = re.search_routes("A", "C", "2026-02-16")
        assert len(results) >= 2

        # Extract feasibility scores
        scores = {r['id']: r['feasibility_score'] for r in results}

        # Reliable route should have higher score
        assert scores.get('route_reliable', 0) > scores.get('route_unreliable', 0)

        # The difference should be approximately weight * (1 - unreliable) = 0.25 * (1 - 0.3) = 0.175
        expected_penalty = 0.25 * (1 - 0.3)  # 0.175
        actual_diff = scores['route_reliable'] - scores['route_unreliable']
        assert abs(actual_diff - expected_penalty) < 0.01  # small tolerance for floating point

    def test_reliability_metrics_recorded(self, monkeypatch):
        """Test that reliability metrics are recorded when feature is enabled"""
        from backend.config import Config
        monkeypatch.setattr(Config, 'ROUTE_RELIABILITY_WEIGHT', 0.25)

        # Mock metrics
        metrics_calls = {'applied': 0, 'avg_rel': [], 'score_delta': []}

        class MockCounter:
            def inc(self): metrics_calls['applied'] += 1

        class MockHistogram:
            def observe(self, val):
                if 'reliability' in str(self):
                    metrics_calls['avg_rel'].append(val)
                else:
                    metrics_calls['score_delta'].append(val)

        monkeypatch.setattr("backend.services.route_engine.RMA_ROUTING_RELIABILITY_APPLIED_TOTAL", MockCounter())
        monkeypatch.setattr("backend.services.route_engine.RMA_ROUTE_AVG_RELIABILITY", MockHistogram())
        monkeypatch.setattr("backend.services.route_engine.RMA_ROUTE_SCORE_DELTA", MockHistogram())

        re = self.setup_routeengine()
        s1 = {"id": "seg_ab", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "test_train", "mode": "train"}
        s2 = {"id": "seg_bc", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "test_train", "mode": "train"}

        re.segments_map = {"seg_ab": s1, "seg_bc": s2}
        re.route_segments = {"route_test": [s1, s2]}

        async def mock_get_train_reliabilities(train_ids):
            return {"test_train": 0.8}

        monkeypatch.setattr("backend.services.route_engine.get_train_reliabilities", mock_get_train_reliabilities)

        results = re.search_routes("A", "C", "2026-02-16")
        assert len(results) >= 1

        # Check metrics were recorded
        assert metrics_calls['applied'] == 1  # One route processed
        assert 0.8 in metrics_calls['avg_rel']  # Average reliability recorded
        assert -0.05 in metrics_calls['score_delta']  # Penalty: 0.25 * (1-0.8) = 0.05, recorded as negative
