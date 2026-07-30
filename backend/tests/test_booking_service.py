"""
Tests for Booking Service
"""

import pytest
import asyncio
from datetime import datetime, timezone, date
from unittest.mock import Mock, patch, AsyncMock

from services.booking_service import BookingService, BookingState, BookingResult
from schemas.booking import BookingRequest, PassengerDetails


class TestBookingService:
    """Test cases for BookingService."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.get = Mock()
        db.execute = Mock()
        return db
    
    @pytest.fixture
    def booking_service(self, mock_db):
        """Create booking service instance."""
        return BookingService(mock_db)
    
    @pytest.fixture
    def sample_booking_request(self):
        """Create sample booking request."""
        return BookingRequest(
            journey_id="journey-001",
            travel_date="2025-06-15",
            passengers=[
                PassengerDetails(
                    full_name="John Doe",
                    age=30,
                    gender="M",
                    phone_number="9876543210"
                ),
                PassengerDetails(
                    full_name="Jane Doe",
                    age=28,
                    gender="F"
                )
            ],
            class_type="SL",
            payment_method="upi"
        )
    
    def test_generate_idempotency_key(self, booking_service):
        """Test idempotency key generation."""
        key1 = booking_service._generate_idempotency_key(
            "user-123", "journey-001", "2025-06-15"
        )
        key2 = booking_service._generate_idempotency_key(
            "user-123", "journey-001", "2025-06-15"
        )
        key3 = booking_service._generate_idempotency_key(
            "user-456", "journey-001", "2025-06-15"
        )
        
        # Same inputs should produce same key
        assert key1 == key2
        # Different inputs should produce different key
        assert key1 != key3
        # Key should be 64 characters (SHA256 hex)
        assert len(key1) == 64
    
    def test_generate_pnr(self, booking_service):
        """Test PNR number generation."""
        pnr1 = booking_service._generate_pnr()
        pnr2 = booking_service._generate_pnr()
        
        # Should be 10 characters
        assert len(pnr1) == 10
        # Should be alphanumeric
        assert pnr1.isalnum()
        # Should be uppercase
        assert pnr1.isupper()
        # Should be unique
        assert pnr1 != pnr2
    
    @pytest.mark.asyncio
    async def test_validate_booking_request_valid(self, booking_service, sample_booking_request):
        """Test validation of valid booking request."""
        # Should not raise exception
        await booking_service._validate_booking_request(sample_booking_request)
    
    @pytest.mark.asyncio
    async def test_validate_booking_request_too_many_passengers(self, booking_service):
        """Test validation rejects too many passengers."""
        request = BookingRequest(
            journey_id="journey-001",
            travel_date="2025-06-15",
            passengers=[
                PassengerDetails(full_name=f"Passenger {i}", age=30, gender="M")
                for i in range(7)  # More than 6
            ],
            class_type="SL",
            payment_method="upi"
        )
        
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await booking_service._validate_booking_request(request)
        
        assert exc_info.value.status_code == 400
        assert "6 passengers" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_validate_booking_request_past_date(self, booking_service):
        """Test validation rejects past dates."""
        request = BookingRequest(
            journey_id="journey-001",
            travel_date="2020-01-01",  # Past date
            passengers=[
                PassengerDetails(full_name="John", age=30, gender="M")
            ],
            class_type="SL",
            payment_method="upi"
        )
        
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await booking_service._validate_booking_request(request)
        
        assert exc_info.value.status_code == 400
        assert "past" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_create_booking_new_booking(self, booking_service, mock_db, sample_booking_request):
        """Test creating a new booking."""
        # Mock dependencies
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.get.return_value = None
        
        with patch.object(booking_service, '_acquire_lock', new=AsyncMock(return_value=True)):
            with patch.object(booking_service, '_release_lock', new=AsyncMock()):
                with patch.object(booking_service, '_validate_booking_request', new=AsyncMock()):
                    with patch('services.fraud_detection.fraud_detection_service.assess_risk', new=AsyncMock(return_value=Mock(allowed=True))):
                        with patch.object(booking_service, '_create_booking_record', new=AsyncMock(return_value=Mock(
                            id="booking-123",
                            pnr_number="ABC123",
                            booking_status="initiated",
                            total_amount=1000,
                            payment_url="/payment/123"
                        ))):
                            with patch.object(booking_service, '_allocate_seats', new=AsyncMock(return_value=Mock(
                                status="allocated",
                                seat_ids=["S1", "S2"],
                                price=1000
                            ))):
                                with patch('services.pricing_service.pricing_service.calculate_fare', new=AsyncMock(return_value=1000)):
                                    with patch.object(booking_service, '_initiate_payment', new=AsyncMock(return_value="/payment/123")):
                                        result = await booking_service.create_booking(
                                            sample_booking_request,
                                            "user-123"
                                        )
        
        assert result.booking_id == "booking-123"
        assert result.pnr_number == "ABC123"
        assert result.status == BookingState.PAYMENT_PENDING
        assert result.total_amount == 1000
        assert result.payment_url == "/payment/123"
    
    @pytest.mark.asyncio
    async def test_create_booking_idempotency(self, booking_service, mock_db, sample_booking_request):
        """Test idempotency - returns existing booking."""
        existing_booking = Mock(
            id="existing-booking",
            pnr_number="EXISTING",
            booking_status="payment_pending",
            amount_paid=1000
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = existing_booking
        
        result = await booking_service.create_booking(sample_booking_request, "user-123")
        
        assert result.booking_id == "existing-booking"
        assert result.pnr_number == "EXISTING"
    
    @pytest.mark.asyncio
    async def test_create_booking_lock_contention(self, booking_service, mock_db, sample_booking_request):
        """Test booking when lock cannot be acquired."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        
        with patch.object(booking_service, '_acquire_lock', new=AsyncMock(return_value=False)):
            result = await booking_service.create_booking(sample_booking_request, "user-123")
        
        assert result.status == BookingState.FAILED
        assert "Another booking operation" in result.error


class TestBookingStateMachine:
    """Test booking state machine transitions."""
    
    def test_valid_transitions(self):
        """Test valid state transitions."""
        # From INITIATED can go to VALIDATING or CANCELLED
        assert BookingState.VALIDATING in VALID_TRANSITIONS[BookingState.INITIATED]
        assert BookingState.CANCELLED in VALID_TRANSITIONS[BookingState.INITIATED]
        
        # From CONFIRMED can only go to CANCELLED
        assert BookingState.CANCELLED in VALID_TRANSITIONS[BookingState.CONFIRMED]
        assert len(VALID_TRANSITIONS[BookingState.CONFIRMED]) == 1
    
    def test_terminal_states(self):
        """Test terminal states have no transitions."""
        assert VALID_TRANSITIONS[BookingState.CANCELLED] == []
        assert VALID_TRANSITIONS[BookingState.FAILED] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])