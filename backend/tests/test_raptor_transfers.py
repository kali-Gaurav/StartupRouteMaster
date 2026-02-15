from datetime import date

from backend.services.route_engine import RouteEngine
from backend.config import Config


def test_single_transfer_respects_transfer_window():
    re = RouteEngine()
    # Stations A -> B -> C
    re.stations_map = {"A": {}, "B": {}, "C": {}}

    # First leg: A->B departs 08:00 arrives 09:00
    seg_ab = {
        "id": "ab",
        "source_station_id": "A",
        "dest_station_id": "B",
        "departure": "08:00",
        "arrival": "09:00",
        "duration": 60,
        "cost": 50,
        "operating_days": "1111111",
        "arrival_day_offset": 0,
    }

    # Second leg: B->C departures at 09:05 (within small transfer window) and at 12:00 (outside)
    seg_bc_soon = {
        "id": "bc_soon",
        "source_station_id": "B",
        "dest_station_id": "C",
        "departure": "09:05",
        "arrival": "10:00",
        "duration": 55,
        "cost": 30,
        "operating_days": "1111111",
        "arrival_day_offset": 0,
    }

    seg_bc_late = {
        "id": "bc_late",
        "source_station_id": "B",
        "dest_station_id": "C",
        "departure": "12:00",
        "arrival": "13:00",
        "duration": 60,
        "cost": 20,
        "operating_days": "1111111",
        "arrival_day_offset": 0,
    }

    re.route_segments = {
        "route1": [seg_ab],
        "route2": [seg_bc_soon],
        "route3": [seg_bc_late],
    }

    # fill segments_map for reconstruction
    re.segments_map = {s["id"]: s for s in [seg_ab, seg_bc_soon, seg_bc_late]}
    re._build_route_indices()

    # Set tight transfer window: min 0, max 15 minutes
    old_min = getattr(Config, "TRANSFER_WINDOW_MIN", None)
    old_max = getattr(Config, "TRANSFER_WINDOW_MAX", None)
    Config.TRANSFER_WINDOW_MIN = 0
    Config.TRANSFER_WINDOW_MAX = 15

    try:
        paths = re._raptor_mvp("A", "C", date.today(), max_rounds=1)
        # only the quick connection should be returned
        assert len(paths) == 1
        assert paths[0][0]["id"] == "ab"
        assert paths[0][1]["id"] == "bc_soon"
    finally:
        # restore
        if old_min is None:
            delattr(Config, "TRANSFER_WINDOW_MIN")
        else:
            Config.TRANSFER_WINDOW_MIN = old_min
        if old_max is None:
            delattr(Config, "TRANSFER_WINDOW_MAX")
        else:
            Config.TRANSFER_WINDOW_MAX = old_max


def test_day_offset_allows_overnight_connection():
    re = RouteEngine()
    re.stations_map = {"A": {}, "B": {}, "C": {}}

    # First leg: departs 23:30 arrives 01:10 (arrival_day_offset=1)
    seg_ab = {
        "id": "ab_night",
        "source_station_id": "A",
        "dest_station_id": "B",
        "departure": "23:30",
        "arrival": "01:10",
        "duration": 100,
        "cost": 70,
        "operating_days": "1111111",
        "arrival_day_offset": 1,
    }

    # Second leg: B->C departs 02:00 same day offset
    seg_bc = {
        "id": "bc_after",
        "source_station_id": "B",
        "dest_station_id": "C",
        "departure": "02:00",
        "arrival": "03:00",
        "duration": 60,
        "cost": 40,
        "operating_days": "1111111",
        "arrival_day_offset": 1,
    }

    re.route_segments = {"r1": [seg_ab], "r2": [seg_bc]}
    re.segments_map = {"ab_night": seg_ab, "bc_after": seg_bc}
    re._build_route_indices()

    # generous transfer window
    old_min = getattr(Config, "TRANSFER_WINDOW_MIN", None)
    old_max = getattr(Config, "TRANSFER_WINDOW_MAX", None)
    Config.TRANSFER_WINDOW_MIN = 0
    Config.TRANSFER_WINDOW_MAX = 6 * 60

    try:
        paths = re._raptor_mvp("A", "C", date.today(), max_rounds=1)
        assert len(paths) == 1
        ids = [seg["id"] for seg in paths[0]]
        assert ids == ["ab_night", "bc_after"]
    finally:
        if old_min is None:
            delattr(Config, "TRANSFER_WINDOW_MIN")
        else:
            Config.TRANSFER_WINDOW_MIN = old_min
        if old_max is None:
            delattr(Config, "TRANSFER_WINDOW_MAX")
        else:
            Config.TRANSFER_WINDOW_MAX = old_max
