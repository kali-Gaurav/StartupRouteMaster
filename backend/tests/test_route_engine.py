import pytest
from utils.time_utils import (
    time_string_to_minutes,
    minutes_to_time_string,
    calculate_duration,
    format_duration,
    get_day_of_week,
    is_operating_on_day,
)
from utils.graph_utils import TimeExpandedGraph, haversine_distance
from utils.validators import (
    validate_date,
    validate_phone,
    validate_budget,
    validate_operating_days,
)


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
    """Test graph utility functions."""

    def test_haversine_distance(self):
        distance = haversine_distance(
            lat1=19.0760,
            lon1=72.8777,
            lat2=15.2993,
            lon2=73.8243,
        )
        assert 400 < distance < 450

    def test_time_expanded_graph_creation(self):
        graph = TimeExpandedGraph()
        graph.add_station("station1", 19.0760, 72.8777)
        graph.add_station("station2", 15.2993, 73.8243)

        assert "station1" in graph.station_coords
        assert "station2" in graph.station_coords

    def test_time_expanded_graph_edge(self):
        graph = TimeExpandedGraph()

        graph.add_edge(
            from_station="station1",
            from_time=600,
            to_station="station2",
            to_time=1320,
            cost=450.0,
            duration=720,
            segment_id="segment1",
        )

        assert ("station1", 600) in graph.nodes
        assert ("station2", 1320) in graph.nodes

    def test_heuristic_calculation(self):
        graph = TimeExpandedGraph()
        graph.add_station("mumbai", 19.0760, 72.8777)
        graph.add_station("goa", 15.2993, 73.8243)

        heuristic = graph.get_heuristic("mumbai", "goa")
        assert heuristic > 0


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
