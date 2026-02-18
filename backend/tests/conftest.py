"""
Pytest configuration and shared fixtures for all tests
"""
import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session

from backend.database import SessionLocal, Base, engine_write
from backend.models import User, Stop, Trip, Calendar, Route, StopTime, Agency


@pytest.fixture(scope="session")
def test_db_setup():
    """Set up test database once per test session"""
    # Create all tables
    Base.metadata.create_all(bind=engine_write)
    yield
    # Clean up after all tests
    Base.metadata.drop_all(bind=engine_write)


@pytest.fixture
def db_session(test_db_setup):
    """Create a new database session for each test"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user = User(
        id="test_user_sample",
        email="sample@test.com",
        phone_number="+919876543210",
        password_hash="hashed_password_123",
        role="user",
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_agency(db_session):
    """Create a sample agency for testing"""
    agency = Agency(
        agency_id="TEST_AGENCY_001",
        name="Test Railway Corporation",
        url="https://testcorp.com",
        timezone="Asia/Kolkata",
        language="en"
    )
    db_session.add(agency)
    db_session.commit()
    return agency


@pytest.fixture
def sample_stops(db_session, sample_agency):
    """Create sample stops for testing"""
    stops = [
        Stop(
            stop_id="NDLS",
            code="NDLS",
            name="New Delhi",
            city="Delhi",
            state="Delhi",
            latitude=28.6431,
            longitude=77.1064,
            geom="SRID=4326;POINT(77.1064 28.6431)",
            location_type=1,
            safety_score=85.0,
            is_major_junction=True,
            facilities_json={"wifi": True, "food": True, "rest_room": True}
        ),
        Stop(
            stop_id="MMCT",
            code="MMCT",
            name="Mumbai Central",
            city="Mumbai",
            state="Maharashtra",
            latitude=18.9688,
            longitude=72.8194,
            geom="SRID=4326;POINT(72.8194 18.9688)",
            location_type=1,
            safety_score=78.0,
            is_major_junction=True,
            facilities_json={"wifi": True, "food": True, "rest_room": True}
        ),
        Stop(
            stop_id="PUNE",
            code="PUNE",
            name="Pune Junction",
            city="Pune",
            state="Maharashtra",
            latitude=18.5286,
            longitude=73.8395,
            geom="SRID=4326;POINT(73.8395 18.5286)",
            location_type=1,
            safety_score=72.0,
            is_major_junction=False,
            facilities_json={"wifi": False, "food": True, "rest_room": False}
        ),
        Stop(
            stop_id="BLR",
            code="BLRC",
            name="Bangalore City Junction",
            city="Bangalore",
            state="Karnataka",
            latitude=12.9716,
            longitude=77.5946,
            geom="SRID=4326;POINT(77.5946 12.9716)",
            location_type=1,
            safety_score=75.0,
            is_major_junction=True,
            facilities_json={"wifi": True, "food": True, "rest_room": True}
        ),
    ]
    db_session.add_all(stops)
    db_session.commit()
    return {s.stop_id: s for s in stops}


@pytest.fixture
def sample_calendar(db_session):
    """Create sample calendar for testing"""
    calendar = Calendar(
        service_id="WKD_001",
        monday=True,
        tuesday=True,
        wednesday=True,
        thursday=True,
        friday=True,
        saturday=True,
        sunday=True,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365)
    )
    db_session.add(calendar)
    db_session.commit()
    return calendar


@pytest.fixture
def sample_route(db_session, sample_agency):
    """Create sample route for testing"""
    route = Route(
        route_id="TRAIN_RAJ_001",
        agency_id=sample_agency.id,
        short_name="RJ",
        long_name="Rajdhani Express",
        description="Premium high-speed express",
        route_type=2,  # Rail
        url="https://route.com"
    )
    db_session.add(route)
    db_session.commit()
    return route


@pytest.fixture
def sample_trip(db_session, sample_route, sample_calendar):
    """Create sample trip for testing"""
    trip = Trip(
        trip_id="TRIP_RAJ_001",
        route_id=sample_route.id,
        service_id=sample_calendar.service_id,
        headsign="New Delhi",
        direction_id=0,
        bike_allowed=False,
        wheelchair_accessible=True,
        trip_headsign="New Delhi"
    )
    db_session.add(trip)
    db_session.commit()
    return trip


@pytest.fixture
def sample_stop_times(db_session, sample_trip, sample_stops):
    """Create sample stop times for testing"""
    from datetime import datetime
    
    stop_times = [
        StopTime(
            trip_id=sample_trip.id,
            stop_id=sample_stops["MMCT"].id,
            arrival_time=datetime.strptime("06:00", "%H:%M").time(),
            departure_time=datetime.strptime("06:20", "%H:%M").time(),
            stop_sequence=1,
            cost=0.0,
            pickup_type=0,
            drop_off_type=0,
            platform_number="1"
        ),
        StopTime(
            trip_id=sample_trip.id,
            stop_id=sample_stops["PUNE"].id,
            arrival_time=datetime.strptime("10:00", "%H:%M").time(),
            departure_time=datetime.strptime("10:15", "%H:%M").time(),
            stop_sequence=2,
            cost=500.0,
            pickup_type=0,
            drop_off_type=0,
            platform_number="2"
        ),
        StopTime(
            trip_id=sample_trip.id,
            stop_id=sample_stops["NDLS"].id,
            arrival_time=datetime.strptime("16:00", "%H:%M").time(),
            departure_time=datetime.strptime("16:00", "%H:%M").time(),
            stop_sequence=3,
            cost=1000.0,
            pickup_type=0,
            drop_off_type=0,
            platform_number="1"
        ),
    ]
    db_session.add_all(stop_times)
    db_session.commit()
    return stop_times


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "edge_case: mark test as edge case scenario"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "concurrency: mark test as concurrency test"
    )
