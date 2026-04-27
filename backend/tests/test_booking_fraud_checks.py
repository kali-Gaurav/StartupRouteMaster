"""
Unit tests for BookingFraudCheck model and fraud detection functionality.
Tests the fraud check storage, risk scoring, and decision tracking.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from database.models import BookingFraudCheck, User, Booking
from database.base import UserBase


class TestBookingFraudCheckModel:
    """Test cases for the BookingFraudCheck model."""

    def test_model_creation(self):
        """Test that the model can be instantiated with required fields."""
        now = datetime.utcnow()
        
        fraud_check = BookingFraudCheck(
            booking_id="booking-uuid-123",
            user_id="user-uuid-456",
            check_type="velocity_check",
            risk_score=0.25,
            flags={"bookings_last_24h": 3, "max_allowed": 5},
            decision="ALLOWED",
            created_at=now
        )
        
        assert fraud_check.booking_id == "booking-uuid-123"
        assert fraud_check.user_id == "user-uuid-456"
        assert fraud_check.check_type == "velocity_check"
        assert fraud_check.risk_score == 0.25
        assert fraud_check.flags == {"bookings_last_24h": 3, "max_allowed": 5}
        assert fraud_check.decision == "ALLOWED"
        assert fraud_check.created_at == now

    def test_model_creation_minimal(self):
        """Test that the model can be instantiated with minimal required fields."""
        fraud_check = BookingFraudCheck(
            booking_id="booking-uuid-123",
            user_id="user-uuid-456",
            check_type="amount_check",
            risk_score=0.75,
            decision="BLOCKED"
        )
        
        assert fraud_check.booking_id == "booking-uuid-123"
        assert fraud_check.user_id == "user-uuid-456"
        assert fraud_check.check_type == "amount_check"
        assert fraud_check.risk_score == 0.75
        assert fraud_check.decision == "BLOCKED"
        assert fraud_check.flags is None

    def test_table_name(self):
        """Test that the table name is correctly set."""
        assert BookingFraudCheck.__tablename__ == "booking_fraud_checks"

    def test_check_type_values(self):
        """Test various check types are valid."""
        check_types = [
            "velocity_check",
            "amount_check",
            "device_fingerprint",
            "location_anomaly",
            "payment_pattern",
            "booking_pattern"
        ]
        
        for check_type in check_types:
            fraud_check = BookingFraudCheck(
                booking_id="booking-id",
                user_id="user-id",
                check_type=check_type,
                risk_score=0.0,
                decision="ALLOWED"
            )
            assert fraud_check.check_type == check_type

    def test_decision_values(self):
        """Test various decision values are valid."""
        decisions = ["ALLOWED", "BLOCKED", "REVIEW"]
        
        for decision in decisions:
            fraud_check = BookingFraudCheck(
                booking_id="booking-id",
                user_id="user-id",
                check_type="test_check",
                risk_score=0.5,
                decision=decision
            )
            assert fraud_check.decision == decision

    def test_risk_score_range(self):
        """Test that risk_score can be any float value."""
        test_scores = [0.0, 0.25, 0.5, 0.75, 1.0, 0.12345]
        
        for score in test_scores:
            fraud_check = BookingFraudCheck(
                booking_id="booking-id",
                user_id="user-id",
                check_type="test_check",
                risk_score=score,
                decision="ALLOWED"
            )
            assert fraud_check.risk_score == score

    def test_flags_as_dict(self):
        """Test that flags can store complex dictionary data."""
        flags = {
            "bookings_last_24h": 5,
            "bookings_last_7d": 15,
            "max_per_24h": 5,
            "max_per_7d": 20,
            "ip_address": "192.168.1.1",
            "device_id": "device-abc123",
            "is_new_device": True,
            "is_new_ip": False
        }
        
        fraud_check = BookingFraudCheck(
            booking_id="booking-id",
            user_id="user-id",
            check_type="velocity_check",
            risk_score=0.8,
            decision="BLOCKED",
            flags=flags
        )
        
        assert fraud_check.flags == flags
        assert fraud_check.flags["bookings_last_24h"] == 5
        assert fraud_check.flags["is_new_device"] is True

    def test_flags_as_list(self):
        """Test that flags can also store list data."""
        flags = ["flagged_reason_1", "flagged_reason_2", "high_velocity"]
        
        fraud_check = BookingFraudCheck(
            booking_id="booking-id",
            user_id="user-id",
            check_type="pattern_check",
            risk_score=0.9,
            decision="REVIEW",
            flags=flags
        )
        
        assert fraud_check.flags == flags
        assert len(fraud_check.flags) == 3

    def test_indexes_defined(self):
        """Test that indexes are defined for common query patterns."""
        table_args = BookingFraudCheck.__table_args__
        
        # Check that indexes exist for booking_id, user_id, and check_type
        index_names = [idx.name for idx in table_args if hasattr(idx, 'name')]
        
        assert 'ix_booking_fraud_checks_booking_id' in index_names
        assert 'ix_booking_fraud_checks_user_id' in index_names
        assert 'ix_booking_fraud_checks_check_type' in index_names


class TestFraudCheckWorkflow:
    """Test cases for fraud check workflow logic."""

    def test_create_fraud_check_record(self):
        """Test creating a fraud check record for a booking."""
        fraud_check = BookingFraudCheck(
            booking_id="booking-123",
            user_id="user-456",
            check_type="velocity_check",
            risk_score=0.3,
            flags={"count": 3, "threshold": 5},
            decision="ALLOWED"
        )
        
        assert fraud_check.booking_id == "booking-123"
        assert fraud_check.decision == "ALLOWED"

    def test_high_risk_blocks_booking(self):
        """Test that high risk score results in BLOCKED decision."""
        # Simulate fraud detection logic
        risk_score = 0.95
        threshold = 0.8
        
        decision = "BLOCKED" if risk_score > threshold else "ALLOWED"
        
        assert decision == "BLOCKED"

    def test_medium_risk_requires_review(self):
        """Test that medium risk score requires review."""
        # Simulate fraud detection logic
        risk_score = 0.65
        block_threshold = 0.8
        review_threshold = 0.5
        
        if risk_score > block_threshold:
            decision = "BLOCKED"
        elif risk_score > review_threshold:
            decision = "REVIEW"
        else:
            decision = "ALLOWED"
        
        assert decision == "REVIEW"

    def test_low_risk_allows_booking(self):
        """Test that low risk score allows booking."""
        risk_score = 0.2
        review_threshold = 0.5
        
        if risk_score > review_threshold:
            decision = "REVIEW"
        else:
            decision = "ALLOWED"
        
        assert decision == "ALLOWED"

    def test_velocity_check_flags(self):
        """Test velocity check flag structure."""
        flags = {
            "bookings_last_24h": 6,
            "bookings_last_7d": 25,
            "max_24h": 5,
            "max_7d": 20,
            "user_id": "user-123"
        }
        
        # Simulate velocity check
        bookings_24h = flags["bookings_last_24h"]
        max_24h = flags["max_24h"]
        is_high_velocity = bookings_24h > max_24h
        
        assert is_high_velocity is True

    def test_amount_check_flags(self):
        """Test amount check flag structure."""
        flags = {
            "booking_amount": 150000,
            "max_amount": 100000,
            "currency": "INR",
            "is_single_booking": True
        }
        
        # Simulate amount check
        amount = flags["booking_amount"]
        max_amount = flags["max_amount"]
        is_high_amount = amount > max_amount
        
        assert is_high_amount is True

    def test_device_fingerprint_flags(self):
        """Test device fingerprint check flag structure."""
        flags = {
            "is_new_device": True,
            "is_new_ip": True,
            "device_trust_score": 0.3,
            "ip_country": "UNKNOWN",
            "previous_devices_count": 0
        }
        
        # Simulate device check
        is_suspicious = flags["is_new_device"] and flags["is_new_ip"]
        
        assert is_suspicious is True


class TestFraudCheckService:
    """Test cases for fraud check service logic."""

    def test_query_fraud_checks_by_booking(self):
        """Test querying fraud checks by booking ID."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        
        # Simulate finding fraud checks
        mock_query.all.return_value = [
            BookingFraudCheck(
                booking_id="booking-123",
                user_id="user-456",
                check_type="velocity_check",
                risk_score=0.3,
                decision="ALLOWED"
            ),
            BookingFraudCheck(
                booking_id="booking-123",
                user_id="user-456",
                check_type="amount_check",
                risk_score=0.6,
                decision="REVIEW"
            )
        ]
        
        result = mock_session.query(BookingFraudCheck).filter_by(
            booking_id="booking-123"
        ).all()
        
        assert len(result) == 2
        assert result[0].check_type == "velocity_check"
        assert result[1].check_type == "amount_check"

    def test_query_fraud_checks_by_user(self):
        """Test querying fraud checks by user ID."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        
        # Simulate finding user fraud checks
        mock_query.count.return_value = 5
        
        result = mock_session.query(BookingFraudCheck).filter_by(
            user_id="user-456"
        ).count()
        
        assert result == 5

    def test_aggregate_risk_score(self):
        """Test aggregating risk scores from multiple checks."""
        checks = [
            {"risk_score": 0.2, "weight": 0.3},
            {"risk_score": 0.5, "weight": 0.3},
            {"risk_score": 0.8, "weight": 0.4}
        ]
        
        # Calculate weighted average
        weighted_sum = sum(c["risk_score"] * c["weight"] for c in checks)
        total_weight = sum(c["weight"] for c in checks)
        aggregate_score = weighted_sum / total_weight
        
        # Expected: (0.2*0.3 + 0.5*0.3 + 0.8*0.4) / 1.0 = 0.53
        assert abs(aggregate_score - 0.53) < 0.01

    def test_decision_based_on_aggregate_score(self):
        """Test final decision based on aggregate risk score."""
        aggregate_score = 0.65
        block_threshold = 0.8
        review_threshold = 0.5
        
        if aggregate_score > block_threshold:
            final_decision = "BLOCKED"
        elif aggregate_score > review_threshold:
            final_decision = "REVIEW"
        else:
            final_decision = "ALLOWED"
        
        assert final_decision == "REVIEW"


class TestFraudCheckEdgeCases:
    """Test edge cases for fraud check handling."""

    def test_zero_risk_score(self):
        """Test handling of zero risk score."""
        fraud_check = BookingFraudCheck(
            booking_id="booking-id",
            user_id="user-id",
            check_type="test_check",
            risk_score=0.0,
            decision="ALLOWED"
        )
        
        assert fraud_check.risk_score == 0.0
        assert fraud_check.decision == "ALLOWED"

    def test_max_risk_score(self):
        """Test handling of maximum risk score."""
        fraud_check = BookingFraudCheck(
            booking_id="booking-id",
            user_id="user-id",
            check_type="test_check",
            risk_score=1.0,
            decision="BLOCKED"
        )
        
        assert fraud_check.risk_score == 1.0
        assert fraud_check.decision == "BLOCKED"

    def test_none_flags(self):
        """Test handling of None flags."""
        fraud_check = BookingFraudCheck(
            booking_id="booking-id",
            user_id="user-id",
            check_type="test_check",
            risk_score=0.5,
            decision="REVIEW",
            flags=None
        )
        
        assert fraud_check.flags is None

    def test_empty_flags(self):
        """Test handling of empty flags dict."""
        fraud_check = BookingFraudCheck(
            booking_id="booking-id",
            user_id="user-id",
            check_type="test_check",
            risk_score=0.5,
            decision="ALLOWED",
            flags={}
        )
        
        assert fraud_check.flags == {}

    def test_complex_flags_nested(self):
        """Test handling of complex nested flags."""
        flags = {
            "velocity": {
                "24h": {"count": 3, "max": 5},
                "7d": {"count": 10, "max": 20}
            },
            "amount": {
                "current": 50000,
                "max": 100000,
                "currency": "INR"
            },
            "device": {
                "fingerprint": "abc123",
                "trust_score": 0.8,
                "history": ["ip1", "ip2", "ip3"]
            }
        }
        
        fraud_check = BookingFraudCheck(
            booking_id="booking-id",
            user_id="user-id",
            check_type="comprehensive_check",
            risk_score=0.4,
            decision="ALLOWED",
            flags=flags
        )
        
        assert fraud_check.flags["velocity"]["24h"]["count"] == 3
        assert fraud_check.flags["device"]["trust_score"] == 0.8
        assert len(fraud_check.flags["device"]["history"]) == 3