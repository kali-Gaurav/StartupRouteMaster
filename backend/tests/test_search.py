import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base, Station, Segment
from backend.core.route_engine import RouteEngine


@pytest.fixture
def test_db():
    """Create test database (sqlite in-memory). Avoid geoalchemy2 DDL calls for sqlite."""
    engine = create_engine("sqlite:///:memory:")

    # Temporarily disable geoalchemy2 sqlite after_create hook which expects SpatiaLite
    try:
        import geoalchemy2.dialects.sqlite as _gasqlite
        _orig_after_create = getattr(_gasqlite, 'after_create', None)
        _gasqlite.after_create = lambda *a, **kw: None
    except Exception:
        _orig_after_create = None

    Base.metadata.create_all(bind=engine)

    if _orig_after_create is not None:
        _gasqlite.after_create = _orig_after_create

    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def sample_stations(test_db):
    """Add sample stations."""
    stations = [
        Station(name="Mumbai", city="Mumbai", latitude=19.0760, longitude=72.8777),
        Station(name="Goa", city="Goa", latitude=15.2993, longitude=73.8243),
        Station(name="Delhi", city="Delhi", latitude=28.7041, longitude=77.1025),
    ]
    for station in stations:
        test_db.add(station)
    test_db.commit()
    return stations


@pytest.fixture
def sample_segments(test_db, sample_stations):
    """Add sample segments."""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    segments = [
        Segment(
            source_station_id=sample_stations[0].id,
            dest_station_id=sample_stations[1].id,
            transport_mode="Train",
            departure_time="10:00",
            arrival_time="22:00",
            duration_minutes=720,
            cost=450.0,
            operator="Konkan Kanya Express",
            operating_days="1111111",
        ),
    ]
    for segment in segments:
        test_db.add(segment)
    test_db.commit()
    return segments


def test_route_engine_initialization(test_db, sample_stations, sample_segments):
    """Test route engine can be initialized."""
    engine = RouteEngine(test_db)
    assert engine.graph is not None
    # Note: stations_map is now built per-search query, not at init.
    # At init, it should be empty since we moved to lazy graph building.
    assert isinstance(engine.stations_map, dict)


def test_station_lookup(test_db, sample_stations):
    """Test station lookup by name."""
    engine = RouteEngine(test_db)
    station = engine._find_station_by_name("Mumbai")
    assert station is not None
    assert station.name == "Mumbai"


def test_station_lookup_case_insensitive(test_db, sample_stations):
    """Test station lookup is case-insensitive."""
    engine = RouteEngine(test_db)
    station = engine._find_station_by_name("mumbai")
    assert station is not None


def test_station_not_found(test_db, sample_stations):
    """Test station lookup returns None for non-existent station."""
    engine = RouteEngine(test_db)
    station = engine._find_station_by_name("NonExistent")
    assert station is None


def test_search_routes_basic(test_db, sample_stations, sample_segments):
    """Test basic route search."""
    engine = RouteEngine(test_db)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    routes = engine.search_routes(
        source="Mumbai",
        destination="Goa",
        travel_date=tomorrow,
        max_results=5,
    )

    assert isinstance(routes, list)


def test_search_routes_nonexistent(test_db, sample_stations, sample_segments):
    """Test search for non-existent route."""
    engine = RouteEngine(test_db)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    routes = engine.search_routes(
        source="NonExistent",
        destination="Goa",
        travel_date=tomorrow,
    )

    assert routes == []


def test_search_routes_budget_filter(test_db, sample_stations, sample_segments):
    """Test search with budget category filter."""
    engine = RouteEngine(test_db)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    routes = engine.search_routes(
        source="Mumbai",
        destination="Goa",
        travel_date=tomorrow,
        budget_category="economy",
    )

    assert isinstance(routes, list)


def test_search_routes_sorting(test_db, sample_stations, sample_segments):
    """Test that routes are sorted by cost."""
    engine = RouteEngine(test_db)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    routes = engine.search_routes(
        source="Mumbai",
        destination="Goa",
        travel_date=tomorrow,
    )

    if len(routes) > 1:
        for i in range(len(routes) - 1):
            assert routes[i]["total_cost"] <= routes[i + 1]["total_cost"]
