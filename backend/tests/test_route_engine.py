import pytest
import asyncio
from utils.time_utils import (
    time_string_to_minutes,
    minutes_to_time_string,
    calculate_duration,
    format_duration,
    get_day_of_week,
    is_operating_on_day,
)
from utils.graph_utils import haversine_distance
from utils.validators import (
    validate_date,
    validate_phone,
    validate_budget,
    validate_operating_days,
)
from config import Config


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
    """Unit tests for the RAPTOR MVP implementation in RouteEngine (updated to async/core API)."""

    def setup_routeengine(self):
        from services.route_engine import route_engine
        # reset internal maps (legacy test harness)
        route_engine.stations_map = {}
        route_engine.segments_map = {}
        route_engine.route_segments = {}
        route_engine.station_name_to_id = {}
        route_engine._is_loaded = True
        return route_engine

    @pytest.mark.asyncio
    async def test_direct_route(self):
        re = self.setup_routeengine()
        # stations
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}}
        re.station_name_to_id = {"a": "S1", "b": "S2"}
        # direct segment S1 -> S2
        seg = {"id": "seg1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "10:00", "duration": 120, "cost": 100.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        re.segments_map = {"seg1": seg}
        re.route_segments = {"route_v1": [seg]}

        from datetime import datetime
        results = await re.search_routes("A", "B", datetime.fromisoformat("2026-02-16"))
        assert len(results) >= 1
        r = results[0]
        # Route object assertions (core API)
        assert len(r.transfers) == 0
        assert r.total_cost == pytest.approx(100.0)
        assert len(r.segments) == 1

    @pytest.mark.asyncio
    async def test_one_transfer(self):
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}, "S3": {"name": "C"}}
        re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3"}

        s1 = {"id": "seg1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 50.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        s2 = {"id": "seg2", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 60.0, "operating_days": "1111111", "vehicle_id": "v2", "mode": "train"}

        re.segments_map = {"seg1": s1, "seg2": s2}
        re.route_segments = {"route_v1": [s1], "route_v2": [s2]}

        from datetime import datetime
        results = await re.search_routes("A", "C", datetime.fromisoformat("2026-02-16"))
        assert len(results) >= 1
        r = results[0]
        assert len(r.transfers) == 1
        assert r.total_cost == pytest.approx(110.0)
        assert len(r.segments) == 2

    @pytest.mark.asyncio
    async def test_two_transfers(self):
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}, "S3": {"name": "C"}, "S4": {"name": "D"}}
        re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3", "d": "S4"}

        s1 = {"id": "seg1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 30.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        s2 = {"id": "seg2", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 35.0, "operating_days": "1111111", "vehicle_id": "v2", "mode": "train"}
        s3 = {"id": "seg3", "source_station_id": "S3", "dest_station_id": "S4", "departure": "11:00", "arrival": "12:00", "duration": 60, "cost": 40.0, "operating_days": "1111111", "vehicle_id": "v3", "mode": "train"}

        re.segments_map = {"seg1": s1, "seg2": s2, "seg3": s3}
        re.route_segments = {"route_v1": [s1], "route_v2": [s2], "route_v3": [s3]}

        from datetime import datetime
        results = await re.search_routes("A", "D", datetime.fromisoformat("2026-02-16"))
        assert len(results) >= 1
        r = results[0]
        assert len(r.transfers) == 2
        assert r.total_cost == pytest.approx(105.0)
        assert len(r.segments) == 3

    @pytest.mark.asyncio
    async def test_transfer_window_enforced(self):
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
            from datetime import datetime
            results = await re.search_routes("A", "C", datetime.fromisoformat("2026-02-16"))
            assert results == []
        finally:
            Config.TRANSFER_WINDOW_MIN = old_min

    @pytest.mark.asyncio
    async def test_overnight_day_offset(self):
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}}
        re.station_name_to_id = {"a": "S1", "b": "S2"}

        # dep 23:30 arr 01:30 (next day)
        seg = {"id": "seg_overnight", "source_station_id": "S1", "dest_station_id": "S2", "departure": "23:30", "arrival": "01:30", "duration": 120, "cost": 80.0, "operating_days": "1111111", "vehicle_id": "v_overnight", "arrival_day_offset": 1, "mode": "train"}
        re.segments_map = {"seg_overnight": seg}
        re.route_segments = {"route_v_overnight": [seg]}

        from datetime import datetime
        results = await re.search_routes("A", "B", datetime.fromisoformat("2026-02-16"))
        assert len(results) >= 1
        r = results[0]
        assert r.total_duration == 120

    @pytest.mark.asyncio
    async def test_operating_days_respected(self):
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}}
        re.station_name_to_id = {"a": "S1", "b": "S2"}

        # operates only on Monday (weekday index 0)
        seg = {"id": "seg_mononly", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 30.0, "operating_days": "1000000", "vehicle_id": "v_mon", "mode": "train"}
        re.segments_map = {"seg_mononly": seg}
        re.route_segments = {"route_v_mon": [seg]}

        from datetime import datetime
        monday = datetime.fromisoformat("2026-02-16")  # Monday
        tuesday = datetime.fromisoformat("2026-02-17") # Tuesday
        assert len(await re.search_routes("A", "B", monday)) >= 1
        assert await re.search_routes("A", "B", tuesday) == []

    @pytest.mark.asyncio
    async def test_build_route_indices_and_search_with_indices(self):
        """Verify search returns correct routes when route_segments are present (adapted for core API)."""
        re = self.setup_routeengine()
        re.stations_map = {"S1": {"name": "A"}, "S2": {"name": "B"}, "S3": {"name": "C"}}
        re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3"}

        # route with two sequential segments
        s1 = {"id": "seg1", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:00", "duration": 60, "cost": 50.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
        s2 = {"id": "seg2", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:30", "arrival": "10:30", "duration": 60, "cost": 60.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}

        re.segments_map = {"seg1": s1, "seg2": s2}
        re.route_segments = {"route_v1": [s1, s2]}

        # Search should return a route composed of the two segments
        from datetime import datetime
        results = await re.search_routes("A", "C", datetime.fromisoformat("2026-02-16"))
        assert len(results) >= 1
        route = results[0]
        assert len(route.segments) == 2
        assert route.total_cost == pytest.approx(110.0)

    def test_cache_invalidation_on_schema_mismatch(self, tmp_path):
        import pickle
        import importlib
        from services import route_engine as re_mod

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
        from services.route_engine import route_engine
        # reset internal maps
        route_engine.stations_map = {}
        route_engine.segments_map = {}
        route_engine.route_segments = {}
        route_engine.station_name_to_id = {}
        route_engine._is_loaded = True
        return route_engine

    @pytest.mark.asyncio
    async def test_pareto_pruning_multiple_options(self):
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
        from config import Config
        old_limit = Config.PARETO_LIMIT
        Config.PARETO_LIMIT = 10
        try:
            from datetime import datetime
            results = await re.search_routes("A", "C", datetime.fromisoformat("2026-02-16"))

            # Should return exactly 2 Pareto-optimal routes:
            assert len(results) == 2

            # Sort by total cost for consistent checking
            results.sort(key=lambda x: x.total_cost)

            # First result should be the cheap transfer route
            cheap_route = results[0]
            assert cheap_route.total_cost == pytest.approx(80.0)
            assert cheap_route.total_duration == 240  # 4 hours
            assert len(cheap_route.segments) == 2

            # Second result should be the direct route
            direct_route = results[1]
            assert direct_route.total_cost == pytest.approx(100.0)
            assert direct_route.total_duration == 120  # 2 hours
            assert len(direct_route.segments) == 1

        finally:
            Config.PARETO_LIMIT = old_limit

    @pytest.mark.asyncio
    async def test_pareto_limit_enforced(self):
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

        from config import Config
        old_limit = Config.PARETO_LIMIT
        Config.PARETO_LIMIT = 3  # Limit to 3 results
        try:
            from datetime import datetime
            results = await re.search_routes("A", "B", datetime.fromisoformat("2026-02-16"))
            # Should return at most PARETO_LIMIT results
            assert len(results) <= 3
            # All returned routes should be Pareto-optimal (no dominated ones)
            for i, route in enumerate(results):
                for other_route in results[i+1:]:
                    assert not (route.total_duration <= other_route.total_duration and
                                  route.total_cost <= other_route.total_cost and
                                  (route.total_duration < other_route.total_duration or
                                   route.total_cost < other_route.total_cost))
        finally:
            Config.PARETO_LIMIT = old_limit


class TestFeasibilityScoring:
    """Tests for feasibility scoring, safety and night-layover penalties."""

    def setup_routeengine(self):
        from services.route_engine import route_engine
        route_engine.stations_map = {}
        route_engine.segments_map = {}
        route_engine.route_segments = {}
        route_engine.station_name_to_id = {}
        route_engine._is_loaded = True
        return route_engine

    @pytest.mark.asyncio
    async def test_safer_layover_preferred(self):
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

        from datetime import datetime
        results = await re.search_routes("A", "C", datetime.fromisoformat("2026-02-16"))
        assert len(results) >= 2

        # Treat `score` on the returned Route dataclass as the feasibility score
        scores = {}
        for r in results:
            # build a human-readable path signature from segment departure station names (if available)
            path_signature = tuple(
                re.stations_map.get(seg.departure_station, {}).get('name') if hasattr(seg, 'departure_station') else seg.get('from')
                for seg in r.segments
            )
            scores[path_signature] = getattr(r, 'score', None)

        route_via_b = scores.get(("A", "B"))
        route_via_d = scores.get(("A", "D"))
        assert route_via_d is not None and route_via_b is not None
        assert route_via_d > route_via_b

    @pytest.mark.asyncio
    async def test_night_layover_penalized(self):
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

        from datetime import datetime
        results = await re.search_routes("A", "C", datetime.fromisoformat("2026-02-16"))
        assert len(results) >= 2

        # Treat `score` on the returned Route dataclass as the feasibility score
        scores = [getattr(r, 'score', None) for r in results]

        # night route must have strictly lower feasibility score due to night-layover penalty
        night_scores = [r.score for r in results if any(
            (hasattr(seg, 'departure_time') and seg.departure_time.strftime('%H:%M') == '22:30') or
            (hasattr(seg, 'arrival_time') and seg.arrival_time.strftime('%H:%M') == '23:30')
            for seg in r.segments
        )]
        day_scores = [r.score for r in results if any(
            (hasattr(seg, 'departure_time') and seg.departure_time.strftime('%H:%M') == '08:00')
            for seg in r.segments
        )]
        assert night_scores and day_scores
        assert max(day_scores) > max(night_scores)
