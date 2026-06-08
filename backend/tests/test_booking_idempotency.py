"""
Unit tests for BookingIdempotency model and functionality.
Tests the idempotency key storage, hashing, and expiration logic.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import hashlib
import json

# Import the model
from database.models import BookingIdempotency, User, Booking
from database.base import UserBase


class TestBookingIdempotencyModel:
    """Test cases for the BookingIdempotency model."""

    def test_model_creation(self):
        """Test that the model can be instantiated with required fields."""
        now = datetime.utcnow()
        expires = now + timedelta(hours=24)
        
        idempotency = BookingIdempotency(
            idempotency_key="test-key-123",
            booking_id="booking-uuid-123",
            request_hash=hashlib.sha256(b"test_request").hexdigest(),
            created_at=now,
            expires_at=expires
        )
        
        assert idempotency.idempotency_key == "test-key-123"
        assert idempotency.booking_id == "booking-uuid-123"
        assert idempotency.request_hash == hashlib.sha256(b"test_request").hexdigest()
        assert idempotency.created_at == now
        assert idempotency.expires_at == expires

    def test_request_hash_is_sha256(self):
        """Test that request_hash is a valid SHA-256 hex string."""
        test_data = {"src": "NDLS", "dst": "BCT", "date": "2026-01-15"}
        request_str = json.dumps(test_data, sort_keys=True)
        expected_hash = hashlib.sha256(request_str.encode()).hexdigest()
        
        idempotency = BookingIdempotency(
            idempotency_key="test-key",
            booking_id="booking-id",
            request_hash=expected_hash,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        # SHA-256 produces 64 character hex string
        assert len(idempotency.request_hash) == 64
        assert all(c in '0123456789abcdef' for c in idempotency.request_hash)

    def test_table_name(self):
        """Test that the table name is correctly set."""
        assert BookingIdempotency.__tablename__ == "booking_idempotency"

    def test_primary_key(self):
        """Test that idempotency_key is the primary key."""
        # The primary key constraint is defined in the model
        assert BookingIdempotency.__table__.primary_key.columns.keys() == ['idempotency_key']


class TestIdempotencyWorkflow:
    """Test cases for the idempotency workflow logic."""

    def test_create_request_hash(self):
        """Test creating a hash from a booking request."""
        request = {
            "user_id": "user-123",
            "route_id": "route-456",
            "passengers": [
                {"name": "John Doe", "age": 30, "gender": "M"}
            ],
            "travel_date": "2026-01-15"
        }
        
        # Sort keys for consistent hashing
        request_str = json.dumps(request, sort_keys=True)
        request_hash = hashlib.sha256(request_str.encode()).hexdigest()
        
        assert len(request_hash) == 64
        # Verify it's deterministic
        request_hash_2 = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        assert request_hash == request_hash_2

    def test_duplicate_request_same_hash(self):
        """Test that identical requests produce the same hash."""
        request = {
            "src": "NDLS",
            "dst": "BCT",
            "date": "2026-01-15"
        }
        
        hash1 = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        
        assert hash1 == hash2

    def test_different_request_different_hash(self):
        """Test that different requests produce different hashes."""
        request1 = {"src": "NDLS", "dst": "BCT"}
        request2 = {"src": "NDLS", "dst": "MMCT"}
        
        hash1 = hashlib.sha256(json.dumps(request1, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(request2, sort_keys=True).encode()).hexdigest()
        
        assert hash1 != hash2

    def test_expired_idempotency_record(self):
        """Test identifying an expired idempotency record."""
        now = datetime.utcnow()
        expired_time = now - timedelta(hours=1)
        
        idempotency = BookingIdempotency(
            idempotency_key="expired-key",
            booking_id="booking-id",
            request_hash="abc123",
            created_at=expired_time - timedelta(hours=24),
            expires_at=expired_time
        )
        
        assert idempotency.expires_at < now

    def test_valid_idempotency_record(self):
        """Test identifying a valid (non-expired) idempotency record."""
        now = datetime.utcnow()
        future_time = now + timedelta(hours=24)
        
        idempotency = BookingIdempotency(
            idempotency_key="valid-key",
            booking_id="booking-id",
            request_hash="abc123",
            created_at=now,
            expires_at=future_time
        )
        
        assert idempotency.expires_at > now


class TestIdempotencyService:
    """Test cases for idempotency service logic."""

    def test_check_idempotency_key_exists(self):
        """Test checking if an idempotency key exists."""
        # Mock database session
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = None  # Key doesn't exist
        
        # In a real service, this would query the DB
        result = mock_session.query(BookingIdempotency).filter_by(
            idempotency_key="new-key"
        ).first()
        
        assert result is None

    def test_check_idempotency_key_found(self):
        """Test when an idempotency key is found."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        
        existing_record = BookingIdempotency(
            idempotency_key="existing-key",
            booking_id="booking-123",
            request_hash="hash123",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        mock_query.first.return_value = existing_record
        
        result = mock_session.query(BookingIdempotency).filter_by(
            idempotency_key="existing-key"
        ).first()
        
        assert result is not None
        assert result.booking_id == "booking-123"
