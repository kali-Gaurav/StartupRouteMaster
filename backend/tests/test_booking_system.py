"""
Test Suite for Seat Inventory & Booking Engine

Tests cover:
- Seat availability checking
- Seat allocation and quota management
- Distributed booking transactions (Saga pattern)
- Waitlist operations
- PNR generation and booking management
- High-concurrency scenarios
"""

import pytest
import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .database import Base, get_db
from .seat_inventory_models import *
from .availability_service import availability_service, AvailabilityRequest
from .booking_orchestrator import booking_orchestrator, BookingRequest
from .config import Config


# Test database setup
@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine"""
    engine = create_engine(Config.TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_session(test_engine):
    """Create test database session"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def sample_trip_data(test_session):
    """Create sample trip and inventory data for testing"""
    # Create sample train
    train = Train(
        train_number="12345",
        train_name="Test Express",
        train_type="Express"
    )
    test_session.add(train)
    test_session.flush()

    # Create coaches
    coaches = []
    for i in range(1, 6):  # 5 coaches
        coach = Coach(
            train_id=train.id,
            coach_number=f"S{i}",
            coach_class=CoachClass.SLEEPER,
            total_seats=72,
            coach_sequence=i
        )
        coaches.append(coach)
        test_session.add(coach)

    test_session.flush()

    # Create seats for each coach
    seats = []
    for coach in coaches:
        for seat_num in range(1, 73):  # 72 seats per coach
            seat = Seat(
                coach_id=coach.id,
                seat_number=f"{seat_num:02d}",
                seat_type="LB" if seat_num % 8 in [1, 4] else "UB" if seat_num % 8 in [2, 5] else "SL" if seat_num % 8 in [3, 6] else "SU",
                is_active=True
            )
            seats.append(seat)
            test_session.add(seat)

    test_session.flush()

    # Create trip
    trip = Trip(
        train_id=train.id,
        trip_date=date.today() + timedelta(days=7),
        status="ACTIVE"
    )
    test_session.add(trip)
    test_session.flush()

    # Create stop times
    stops = [
        StopTime(trip_id=trip.id, stop_id=1, stop_sequence=1, arrival_time="10:00", departure_time="10:05"),
        StopTime(trip_id=trip.id, stop_id=2, stop_sequence=2, arrival_time="12:00", departure_time="12:05"),
        StopTime(trip_id=trip.id, stop_id=3, stop_sequence=3, arrival_time="14:00", departure_time="14:05"),
        StopTime(trip_id=trip.id, stop_id=4, stop_sequence=4, arrival_time="16:00", departure_time=None)
    ]

    for stop in stops:
        test_session.add(stop)

    test_session.flush()

    # Create seat inventory for segments
    segments = []
    for i in range(len(stops) - 1):
        segment = SeatInventory(
            trip_id=trip.id,
            segment_from_stop_id=stops[i].stop_id,
            segment_to_stop_id=stops[i+1].stop_id,
            date=trip.trip_date,
            total_seats=360,  # 5 coaches * 72 seats
            available_seats=360,
            booked_seats=0,
            quota_type=QuotaType.GENERAL
        )
        segments.append(segment)
        test_session.add(segment)

    test_session.flush()

    # Create quota inventory
    for segment in segments:
        for quota in QuotaType:
            quota_inventory = QuotaInventory(
                inventory_id=segment.id,
                quota_type=quota,
                max_allocation=360 if quota == QuotaType.GENERAL else 50,
                available_seats=360 if quota == QuotaType.GENERAL else 50,
                allocated_seats=0
            )
            test_session.add(quota_inventory)

    test_session.commit()

    return {
        'train': train,
        'trip': trip,
        'coaches': coaches,
        'seats': seats,
        'segments': segments,
        'stops': stops
    }


class TestAvailabilityService:
    """Test cases for availability service"""

    @pytest.mark.asyncio
    async def test_check_availability_success(self, test_session, sample_trip_data):
        """Test successful availability check"""
        request = AvailabilityRequest(
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date,
            quota_type=QuotaType.GENERAL,
            passengers=2
        )

        response = await availability_service.check_availability(request)

        assert response.available == True
        assert response.available_seats == 360
        assert response.total_seats == 360
        assert response.confirmation_probability == 1.0

    def test_availability_endpoint_http(self, sample_trip_data):
        """Ensure the FastAPI availability route is reachable and returns expected fields."""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        payload = {
            "trip_id": sample_trip_data['trip'].id,
            "from_stop_id": 1,
            "to_stop_id": 4,
            "travel_date": sample_trip_data['trip'].trip_date.isoformat(),
            "quota_type": "GENERAL",
            "passengers": 2,
        }
        res = client.post("/api/v1/booking/availability", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert isinstance(data.get("available"), bool)
        assert "available_seats" in data
        assert "availability_status" in data
        assert "probability" in data

    @pytest.mark.asyncio
    async def test_check_availability_no_inventory(self, test_session):
        """Test availability check with no inventory"""
        request = AvailabilityRequest(
            trip_id=999,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=date.today() + timedelta(days=30),
            quota_type=QuotaType.GENERAL,
            passengers=1
        )

        response = await availability_service.check_availability(request)

        assert response.available == False
        assert response.available_seats == 0
        assert "No inventory found" in response.message

    @pytest.mark.asyncio
    async def test_allocate_seats_success(self, test_session, sample_trip_data):
        """Test successful seat allocation"""
        request = AvailabilityRequest(
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date,
            quota_type=QuotaType.GENERAL,
            passengers=2
        )

        allocation = await availability_service.allocate_seats(request, "user123", "session123")

        assert allocation is not None
        assert len(allocation.seat_ids) == 2
        assert allocation.coach_number is not None
        assert allocation.quota_type == QuotaType.GENERAL

    @pytest.mark.asyncio
    async def test_allocate_seats_insufficient_inventory(self, test_session, sample_trip_data):
        """Test seat allocation with insufficient inventory"""
        # First allocate most seats
        request1 = AvailabilityRequest(
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date,
            quota_type=QuotaType.GENERAL,
            passengers=359  # Leave only 1 seat
        )

        await availability_service.allocate_seats(request1, "user123", "session123")

        # Try to allocate more than available
        request2 = AvailabilityRequest(
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date,
            quota_type=QuotaType.GENERAL,
            passengers=5
        )

        allocation = await availability_service.allocate_seats(request2, "user456", "session456")

        assert allocation is None

    @pytest.mark.asyncio
    async def test_add_to_waitlist(self, test_session, sample_trip_data):
        """Test adding booking to waitlist"""
        request = AvailabilityRequest(
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date,
            quota_type=QuotaType.GENERAL,
            passengers=400  # More than available
        )

        passengers_json = [
            {"name": "John Doe", "age": 30, "gender": "M"},
            {"name": "Jane Doe", "age": 28, "gender": "F"}
        ]

        position = await availability_service.add_to_waitlist(
            request, "user123", passengers_json
        )

        assert position == 1

        # Add another to waitlist
        position2 = await availability_service.add_to_waitlist(
            request, "user456", passengers_json
        )

        assert position2 == 2


class TestBookingOrchestrator:
    """Test cases for booking orchestrator"""

    @pytest.mark.asyncio
    async def test_successful_booking(self, test_session, sample_trip_data):
        """Test successful booking transaction"""
        booking_request = BookingRequest(
            user_id="user123",
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date.isoformat(),
            quota_type=QuotaType.GENERAL.value,
            passengers=[
                {"name": "John Doe", "age": 30, "gender": "M"},
                {"name": "Jane Doe", "age": 28, "gender": "F"}
            ],
            payment_method={"type": "CARD", "details": {"token": "test_token"}},
            preferences={"meal": "VEG"}
        )

        result = await booking_orchestrator.process_booking(booking_request)

        assert result.success == True
        assert result.pnr_number is not None
        assert len(result.pnr_number) == 10
        assert result.booking_id is not None
        assert result.total_amount is not None

        # validate passenger persistence in database
        from backend.database.models import Booking as BookingModel
        booking = test_session.query(BookingModel).filter(BookingModel.pnr_number == result.pnr_number).first()
        assert booking is not None
        assert len(booking.passenger_details) == 2

    @pytest.mark.asyncio
    async def test_booking_insufficient_seats(self, test_session, sample_trip_data):
        """Test booking failure due to insufficient seats"""
        # First book all available seats
        booking_request1 = BookingRequest(
            user_id="user123",
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date.isoformat(),
            quota_type=QuotaType.GENERAL.value,
            passengers=[{"name": f"Passenger {i}", "age": 30, "gender": "M"} for i in range(360)],
            payment_method={"type": "CARD", "details": {"token": "test_token"}},
        )

        await booking_orchestrator.process_booking(booking_request1)

        # Try to book more
        booking_request2 = BookingRequest(
            user_id="user456",
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date.isoformat(),
            quota_type=QuotaType.GENERAL.value,
            passengers=[{"name": "Extra Passenger", "age": 30, "gender": "M"}],
            payment_method={"type": "CARD", "details": {"token": "test_token"}},
        )

        result = await booking_orchestrator.process_booking(booking_request2)

        assert result.success == False
        assert "not available" in result.message.lower()

    @pytest.mark.asyncio
    async def test_booking_cancellation(self, test_session, sample_trip_data):
        """Test booking cancellation"""
        # First create a booking
        booking_request = BookingRequest(
            user_id="user123",
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=(date.today() + timedelta(days=8)).isoformat(),  # Future date
            quota_type=QuotaType.GENERAL.value,
            passengers=[{"name": "John Doe", "age": 30, "gender": "M"}],
            payment_method={"type": "CARD", "details": {"token": "test_token"}},
        )

        booking_result = await booking_orchestrator.process_booking(booking_request)
        assert booking_result.success == True

        # Cancel the booking
        cancel_result = await booking_orchestrator.cancel_booking(
            booking_result.pnr_number, "user123"
        )

        assert cancel_result["success"] == True
        assert "cancelled successfully" in cancel_result["message"]
        assert cancel_result["refund_amount"] is not None

    @pytest.mark.asyncio
    async def test_get_booking_status(self, test_session, sample_trip_data):
        """Test getting booking status"""
        # Create a booking
        booking_request = BookingRequest(
            user_id="user123",
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=(date.today() + timedelta(days=8)).isoformat(),
            quota_type=QuotaType.GENERAL.value,
            passengers=[{"name": "John Doe", "age": 30, "gender": "M"}],
            payment_method={"type": "CARD", "details": {"token": "test_token"}},
        )

        booking_result = await booking_orchestrator.process_booking(booking_request)
        assert booking_result.success == True

        # Get status
        status = await booking_orchestrator.get_booking_status(
            booking_result.pnr_number, "user123"
        )

        assert status is not None
        assert status["pnr_number"] == booking_result.pnr_number
        assert status["status"] == BookingStatus.CONFIRMED.value
        assert status["passengers"] == 1


class TestConcurrency:
    """Test concurrent booking scenarios"""

    @pytest.mark.asyncio
    async def test_concurrent_booking_same_seats(self, test_session, sample_trip_data):
        """Test concurrent booking attempts for same seats"""
        async def book_seat(user_id: str):
            booking_request = BookingRequest(
                user_id=user_id,
                trip_id=sample_trip_data['trip'].id,
                from_stop_id=1,
                to_stop_id=4,
                travel_date=sample_trip_data['trip'].trip_date.isoformat(),
                quota_type=QuotaType.GENERAL.value,
                passengers=[{"name": f"User {user_id}", "age": 30, "gender": "M"}],
                payment_method={"type": "CARD", "details": {"token": "test_token"}},
            )

            return await booking_orchestrator.process_booking(booking_request)

        # Create multiple concurrent booking attempts
        tasks = [book_seat(f"user{i}") for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful bookings
        successful_bookings = [r for r in results if not isinstance(r, Exception) and r.success]

        # Should not exceed available seats
        assert len(successful_bookings) <= 360

    @pytest.mark.asyncio
    async def test_tatkal_concurrent_booking(self, test_session, sample_trip_data):
        """Test Tatkal quota concurrent booking"""
        async def book_tatkal_seat(user_id: str):
            booking_request = BookingRequest(
                user_id=user_id,
                trip_id=sample_trip_data['trip'].id,
                from_stop_id=1,
                to_stop_id=4,
                travel_date=sample_trip_data['trip'].trip_date.isoformat(),
                quota_type=QuotaType.TATKAL.value,
                passengers=[{"name": f"User {user_id}", "age": 30, "gender": "M"}],
                payment_method={"type": "CARD", "details": {"token": "test_token"}},
            )

            return await booking_orchestrator.process_booking(booking_request)

        # Create concurrent Tatkal booking attempts
        tasks = [book_tatkal_seat(f"user{i}") for i in range(60)]  # More than Tatkal quota
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful Tatkal bookings
        successful_bookings = [r for r in results if not isinstance(r, Exception) and r.success]

        # Should not exceed Tatkal quota (50 seats)
        assert len(successful_bookings) <= 50


class TestQuotaManagement:
    """Test quota-specific functionality"""

    @pytest.mark.asyncio
    async def test_quota_allocation(self, test_session, sample_trip_data):
        """Test quota-based seat allocation"""
        # Test General quota
        request_general = AvailabilityRequest(
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date,
            quota_type=QuotaType.GENERAL,
            passengers=10
        )

        response = await availability_service.check_availability(request_general)
        assert response.available == True

        # Test Tatkal quota
        request_tatkal = AvailabilityRequest(
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date,
            quota_type=QuotaType.TATKAL,
            passengers=10
        )

        response = await availability_service.check_availability(request_tatkal)
        assert response.available == True
        assert response.available_seats <= 50  # Tatkal quota limit

    @pytest.mark.asyncio
    async def test_quota_exhaustion(self, test_session, sample_trip_data):
        """Test quota exhaustion handling"""
        # Exhaust Tatkal quota
        for i in range(5):  # 5 bookings of 10 seats each = 50 seats
            request = AvailabilityRequest(
                trip_id=sample_trip_data['trip'].id,
                from_stop_id=1,
                to_stop_id=4,
                travel_date=sample_trip_data['trip'].trip_date,
                quota_type=QuotaType.TATKAL,
                passengers=10
            )

            await availability_service.allocate_seats(request, f"user{i}", f"session{i}")

        # Check Tatkal availability after exhaustion
        check_request = AvailabilityRequest(
            trip_id=sample_trip_data['trip'].id,
            from_stop_id=1,
            to_stop_id=4,
            travel_date=sample_trip_data['trip'].trip_date,
            quota_type=QuotaType.TATKAL,
            passengers=1
        )

        response = await availability_service.check_availability(check_request)
        assert response.available == False or response.available_seats == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])