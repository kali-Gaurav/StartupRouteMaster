import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from worker import reconcile_payments
from models import Booking, Payment
from database import SessionLocal
from services.payment_service import PaymentService


@pytest.fixture
def mock_db_session():
    """Fixture to provide a mock database session."""
    with patch('backend.database.SessionLocal') as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        yield mock_session

@pytest.fixture
def mock_payment_service():
    """Fixture to provide a mock PaymentService."""
    with patch('backend.services.payment_service.PaymentService') as mock_payment_service_class:
        mock_service = MagicMock()
        mock_payment_service_class.return_value = mock_service
        yield mock_service

def create_mock_booking_and_payment(payment_status="pending", razorpay_order_id="order_xyz", booking_id="booking_abc", payment_id="payment_123"):
    """Helper to create mock Booking and Payment objects."""
    mock_payment = Payment(
        id=payment_id,
        booking_id=booking_id,
        razorpay_order_id=razorpay_order_id,
        status=payment_status,
        amount=100.0
    )
    mock_booking = Booking(
        id=booking_id,
        user_id="user_1",
        route_id="route_1",
        travel_date="2026-01-01",
        payment_status=payment_status,
        amount_paid=100.0,
        booking_details={},
        payment_id=payment_id
    )
    return mock_booking, mock_payment


def test_reconcile_payments_no_pending(mock_db_session, mock_payment_service):
    """Test reconciliation when no pending payments exist."""
    mock_db_session.query.return_value.filter.return_value.all.return_value = []
    
    reconcile_payments()
    
    # Ensure no Razorpay API calls are made if there are no pending payments
    mock_payment_service.fetch_order_details.assert_not_called()
    mock_db_session.commit.assert_not_called()

def test_reconcile_payments_successful(mock_db_session, mock_payment_service):
    """Test successful reconciliation of a paid order."""
    mock_booking, mock_payment = create_mock_booking_and_payment()
    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_payment]
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [
        mock_booking, # For booking lookup
    ]
    
    # Simulate Razorpay returning a 'paid' status
    mock_payment_service.fetch_order_details.return_value = {
        "id": mock_payment.razorpay_order_id,
        "status": "paid",
        "payments": [{"id": "pay_razorpay123"}], # Example payment ID from Razorpay
        "amount": 10000 # in paise
    }

    reconcile_payments()

    mock_payment_service.fetch_order_details.assert_called_once_with(mock_payment.razorpay_order_id)
    assert mock_payment.status == "completed"
    assert mock_payment.razorpay_payment_id == "pay_razorpay123"
    assert mock_booking.payment_status == "completed"
    mock_db_session.add.call_count >= 2 # At least for payment and booking
    mock_db_session.commit.assert_called_once()


def test_reconcile_payments_still_pending(mock_db_session, mock_payment_service):
    """Test reconciliation when Razorpay indicates order is still pending/attempted."""
    mock_booking, mock_payment = create_mock_booking_and_payment()
    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_payment]
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [
        mock_booking,
    ]
    
    # Simulate Razorpay returning 'attempted' status
    mock_payment_service.fetch_order_details.return_value = {
        "id": mock_payment.razorpay_order_id,
        "status": "attempted",
        "amount": 10000
    }

    reconcile_payments()

    mock_payment_service.fetch_order_details.assert_called_once_with(mock_payment.razorpay_order_id)
    assert mock_payment.status == "pending" # Should remain pending
    assert mock_booking.payment_status == "pending" # Should remain pending
    mock_db_session.commit.assert_not_called() # No commit if no change


def test_reconcile_payments_razorpay_api_failure(mock_db_session, mock_payment_service):
    """Test reconciliation when Razorpay API call fails."""
    mock_booking, mock_payment = create_mock_booking_and_payment()
    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_payment]
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [
        mock_booking,
    ]
    
    mock_payment_service.fetch_order_details.return_value = None # Simulate API failure

    reconcile_payments()

    mock_payment_service.fetch_order_details.assert_called_once_with(mock_payment.razorpay_order_id)
    assert mock_payment.status == "pending" # Should remain pending
    assert mock_booking.payment_status == "pending" # Should remain pending
    mock_db_session.commit.assert_not_called() # No commit if API fails and no status change

def test_reconcile_payments_booking_already_processed(mock_db_session, mock_payment_service):
    """Test reconciliation ignores bookings already completed."""
    mock_booking_completed, mock_payment_completed = create_mock_booking_and_payment(payment_status="completed")
    mock_booking_failed, mock_payment_failed = create_mock_booking_and_payment(payment_status="failed", booking_id="booking_def", payment_id="payment_456")

    mock_db_session.query.return_value.filter.return_value.all.return_value = [
        mock_payment_completed,
        mock_payment_failed
    ]
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [
        mock_booking_completed, # First call for completed booking
        mock_booking_failed,    # Second call for failed booking
    ]
    
    reconcile_payments()
    
    # Should not call Razorpay for already processed bookings
    mock_payment_service.fetch_order_details.assert_not_called()
    mock_db_session.commit.assert_not_called()
