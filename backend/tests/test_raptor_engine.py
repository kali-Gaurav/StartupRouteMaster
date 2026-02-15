from datetime import date

from backend.services.route_engine import RouteEngine


def test_simple_direct_route():
    re = RouteEngine()
    # Minimal station/route setup: A -> B
    re.stations_map = {"A": {}, "B": {}}
    re.route_segments = {
        "route_1": [
            {
                "id": "seg1",
                "source_station_id": "A",
                "dest_station_id": "B",
                "departure": "08:00",
                "arrival": "09:00",
                "duration": 60,
                "cost": 100,
                "operating_days": "1111111",
                "arrival_day_offset": 0,
            }
        ]
    }
    # Populate segments_map so path reconstruction can look up segment metadata
    re.segments_map = {"seg1": re.route_segments["route_1"][0]}
    re._build_route_indices()

    paths = re._raptor_mvp("A", "B", date.today(), max_rounds=0)
    assert len(paths) == 1
    path = paths[0]
    assert isinstance(path, list)
    assert len(path) == 1
    assert path[0]["id"] == "seg1"


def test_pareto_two_non_dominated_routes():
    re = RouteEngine()
    re.stations_map = {"A": {}, "B": {}}

    # route_fast is faster but more expensive
    route_fast = {
        "id": "fast",
        "source_station_id": "A",
        "dest_station_id": "B",
        "departure": "08:00",
        "arrival": "08:50",
        "duration": 50,
        "cost": 120,
        "operating_days": "1111111",
        "arrival_day_offset": 0,
    }

    # route_cheap is slower but cheaper
    route_cheap = {
        "id": "cheap",
        "source_station_id": "A",
        "dest_station_id": "B",
        "departure": "08:10",
        "arrival": "09:10",
        "duration": 60,
        "cost": 80,
        "operating_days": "1111111",
        "arrival_day_offset": 0,
    }

    re.route_segments = {
        "route_fast": [route_fast],
        "route_cheap": [route_cheap],
    }
    # Populate segments_map for reconstruction
    re.segments_map = {"fast": route_fast, "cheap": route_cheap}
    re._build_route_indices()

    paths = re._raptor_mvp("A", "B", date.today(), max_rounds=0)
    # Both routes should be non-dominated (faster vs cheaper)
    assert len(paths) == 2
    ids = {p[0]["id"] for p in paths}
    assert ids == {"fast", "cheap"}
