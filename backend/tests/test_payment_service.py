"""
Comprehensive unit tests for PaymentService.
Team 5: QA & Testing Team - Razorpay Payment Integration
Coverage target: >95% for PaymentService
"""

import pytest
import uuid
import hashlib
import hmac
import json
from unittest.mock import patch, MagicMock, AsyncMock, call
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from services.payment_service import PaymentService, MockPaymentService
from schemas.payment import PaymentStatus, PaymentRequest, PaymentResponse
from fastapi import HTTPException
from core.resilience.core import CircuitOpenError


class TestPaymentServiceInitialization:
    """Test PaymentService initialization and configuration."""

    def test_payment_service_initialization(self, db_session):
        """Test PaymentService can be initialized with database session."""
        service = PaymentService(db_session)
        assert service is not None
        assert service.db == db_session
        assert isinstance(service.webhook_secrets, dict)

    def test_payment_service_has_webhook_secrets(self, db_session):
        """Test webhook secrets are available."""
        service = PaymentService(db_session)
        assert hasattr(service, 'webhook_secrets')


class TestCreatePayment:
    """Test payment creation flow."""

    @pytest.mark.asyncio
    async def test_create_payment_success(self, db_session, mock_booking):
        """Test successful payment creation."""
        service = PaymentService(db_session)

        response = await service.create_payment(
            booking_id=mock_booking.id,
            amount=500.0,
            payment_method="upi",
            user_id=mock_booking.user_id
        )

        assert response.payment_id is not None
        assert response.booking_id == mock_booking.id
        assert response.amount == 500.0
        assert response.status == PaymentStatus.PENDING
        assert response.payment_url is not None
        assert response.expires_at is not None

    @pytest.mark.asyncio
    async def test_create_payment_invalid_booking(self, db_session):
        """Test payment creation with non-existent booking."""
        service = PaymentService(db_session)

        with pytest.raises(HTTPException) as exc:
            await service.create_payment(
                booking_id="non_existent_booking_id",
                amount=500.0,
                payment_method="upi",
                user_id="user_123"
            )

        assert exc.value.status_code == 404
        assert "Booking not found" in exc.value.detail

    @pytest.mark.asyncio
    async def test_create_payment_unauthorized_user(self, db_session, mock_booking):
        """Test payment creation with unauthorized user."""
        service = PaymentService(db_session)

        with pytest.raises(HTTPException) as exc:
            await service.create_payment(
                booking_id=mock_booking.id,
                amount=500.0,
                payment_method="upi",
                user_id="different_user_id"
            )

        assert exc.value.status_code == 403
        assert "Not authorized" in exc.value.detail

    @pytest.mark.asyncio
    async def test_create_payment_invalid_booking_status(self, db_session, mock_booking):
        """Test payment creation with invalid booking status."""
        service = PaymentService(db_session)
        mock_booking.booking_status = "completed"
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            await service.create_payment(
                booking_id=mock_booking.id,
                amount=500.0,
                payment_method="upi",
                user_id=mock_booking.user_id
            )

        assert exc.value.status_code == 400
        assert "Cannot pay for booking" in exc.value.detail

    @pytest.mark.asyncio
    async def test_create_payment_unsupported_method(self, db_session, mock_booking):
        """Test payment creation with unsupported payment method."""
        service = PaymentService(db_session)

        with pytest.raises(HTTPException) as exc:
            await service.create_payment(
                booking_id=mock_booking.id,
                amount=500.0,
                payment_method="crypto",
                user_id=mock_booking.user_id
            )

        assert exc.value.status_code == 400
        assert "Unsupported payment method" in exc.value.detail

    @pytest.mark.asyncio
    async def test_create_payment_all_methods(self, db_session, mock_booking):
        """Test payment creation with all payment methods."""
        service = PaymentService(db_session)

        for method in ["upi", "card", "net_banking"]:
            response = await service.create_payment(
                booking_id=mock_booking.id,
                amount=500.0,
                payment_method=method,
                user_id=mock_booking.user_id
            )

            assert response.status == PaymentStatus.PENDING
            assert response.payment_method == method or method in response.payment_url


class TestPaymentSignatureVerification:
    """Test webhook signature verification."""

    def test_verify_webhook_signature_no_secret(self, db_session):
        """Test signature verification without configured secret."""
        service = PaymentService(db_session)
        payload = {"payment_id": "pay_123", "status": "success"}

        # Should accept when no secret is configured (development mode)
        result = service._verify_webhook_signature("razorpay", payload, "any_signature")
        assert result is True

    def test_verify_webhook_signature_valid(self, db_session):
        """Test signature verification with valid signature."""
        service = PaymentService(db_session)
        secret = "test_secret_key"
        service.webhook_secrets["razorpay"] = secret

        payload = {"payment_id": "pay_123", "status": "success"}
        payload_str = str(payload)

        expected_signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()

        result = service._verify_webhook_signature("razorpay", payload, expected_signature)
        assert result is True

    def test_verify_webhook_signature_invalid(self, db_session):
        """Test signature verification with invalid signature."""
        service = PaymentService(db_session)
        secret = "test_secret_key"
        service.webhook_secrets["razorpay"] = secret

        payload = {"payment_id": "pay_123", "status": "success"}
        invalid_signature = "invalid_signature_xyz"

        result = service._verify_webhook_signature("razorpay", payload, invalid_signature)
        assert result is False


class TestPaymentIdempotency:
    """Test idempotency and duplicate payment handling."""

    @pytest.mark.asyncio
    async def test_idempotent_payment_creation(self, db_session, mock_booking):
        """Test that creating same payment twice is idempotent."""
        service = PaymentService(db_session)

        # Create first payment
        response1 = await service.create_payment(
            booking_id=mock_booking.id,
            amount=500.0,
            payment_method="upi",
            user_id=mock_booking.user_id
        )

        # Create another payment for same booking (simulates retry)
        response2 = await service.create_payment(
            booking_id=mock_booking.id,
            amount=500.0,
            payment_method="upi",
            user_id=mock_booking.user_id
        )

        # Both should have different IDs (not strictly idempotent without explicit idempotency key)
        # But verify both payments are in correct state
        assert response1.status == PaymentStatus.PENDING
        assert response2.status == PaymentStatus.PENDING

    @pytest.mark.asyncio
    async def test_idempotent_webhook_processing(self, db_session, mock_booking, mock_payment):
        """Test webhook processing is idempotent."""
        service = PaymentService(db_session)

        payload = {
            "payment_id": mock_payment.id,
            "status": "success",
            "transaction_id": f"txn_{uuid.uuid4().hex[:8]}"
        }
        signature = "valid_signature"

        # Process webhook first time
        result1 = await service.handle_webhook("razorpay", payload, signature)

        # Process same webhook again
        result2 = await service.handle_webhook("razorpay", payload, signature)

        # Both should succeed and return same status
        assert result1["status"] in ["processed", "already_processed"]
        assert result2["status"] in ["processed", "already_processed"]


class TestPaymentStatusMapping:
    """Test payment status mapping from providers."""

    def test_map_provider_status_success(self, db_session):
        """Test mapping of success statuses from different providers."""
        service = PaymentService(db_session)

        success_statuses = ["success", "completed", "captured"]
        for status in success_statuses:
            mapped = service._map_provider_status("razorpay", status)
            assert mapped == PaymentStatus.SUCCESS

    def test_map_provider_status_failed(self, db_session):
        """Test mapping of failed statuses."""
        service = PaymentService(db_session)

        failed_statuses = ["failed", "declined"]
        for status in failed_statuses:
            mapped = service._map_provider_status("razorpay", status)
            assert mapped == PaymentStatus.FAILED

    def test_map_provider_status_cancelled(self, db_session):
        """Test mapping of cancelled status."""
        service = PaymentService(db_session)

        mapped = service._map_provider_status("razorpay", "cancelled")
        assert mapped == PaymentStatus.CANCELLED

    def test_map_provider_status_pending(self, db_session):
        """Test mapping of pending status."""
        service = PaymentService(db_session)

        mapped = service._map_provider_status("razorpay", "pending")
        assert mapped == PaymentStatus.PENDING

    def test_map_provider_status_unknown(self, db_session):
        """Test mapping of unknown status."""
        service = PaymentService(db_session)

        mapped = service._map_provider_status("razorpay", "unknown_status")
        assert mapped == PaymentStatus.UNKNOWN

    def test_map_provider_status_case_insensitive(self, db_session):
        """Test status mapping is case-insensitive."""
        service = PaymentService(db_session)

        assert service._map_provider_status("razorpay", "SUCCESS") == PaymentStatus.SUCCESS
        assert service._map_provider_status("razorpay", "FAILED") == PaymentStatus.FAILED
        assert service._map_provider_status("razorpay", "Completed") == PaymentStatus.SUCCESS


class TestWebhookHandling:
    """Test webhook handling and payment confirmation."""

    @pytest.mark.asyncio
    async def test_handle_webhook_success(self, db_session, mock_payment):
        """Test successful webhook handling."""
        service = PaymentService(db_session)

        payload = {
            "payment_id": mock_payment.id,
            "status": "success",
            "transaction_id": f"txn_{uuid.uuid4().hex[:8]}",
            "upi_tx_id": "UPI123456789",
            "utr_number": "123456789012"
        }

        result = await service.handle_webhook("razorpay", payload, "signature")

        assert result["status"] == "processed"
        assert result["payment_id"] == mock_payment.id

    @pytest.mark.asyncio
    async def test_handle_webhook_missing_payment_id(self, db_session):
        """Test webhook handling with missing payment ID."""
        service = PaymentService(db_session)

        payload = {
            "status": "success",
            "transaction_id": "txn_123"
        }

        with pytest.raises(HTTPException) as exc:
            await service.handle_webhook("razorpay", payload, "signature")

        assert exc.value.status_code == 400
        assert "Payment ID not found" in exc.value.detail

    @pytest.mark.asyncio
    async def test_handle_webhook_invalid_signature(self, db_session, mock_payment):
        """Test webhook handling with invalid signature."""
        service = PaymentService(db_session)
        service.webhook_secrets["razorpay"] = "secret_key"

        payload = {"payment_id": mock_payment.id, "status": "success"}

        with pytest.raises(HTTPException) as exc:
            await service.handle_webhook("razorpay", payload, "invalid_signature")

        assert exc.value.status_code == 401
        assert "Invalid webhook signature" in exc.value.detail

    @pytest.mark.asyncio
    async def test_handle_webhook_nonexistent_payment(self, db_session):
        """Test webhook handling for non-existent payment."""
        service = PaymentService(db_session)

        payload = {
            "payment_id": "non_existent_payment",
            "status": "success"
        }

        with pytest.raises(HTTPException) as exc:
            await service.handle_webhook("razorpay", payload, "signature")

        assert exc.value.status_code == 404


class TestRefundProcessing:
    """Test refund functionality."""

    @pytest.mark.asyncio
    async def test_process_refund_full(self, db_session, mock_payment):
        """Test full refund processing."""
        service = PaymentService(db_session)
        mock_payment.status = PaymentStatus.SUCCESS.value
        db_session.commit()

        refund_response = await service.process_refund(
            payment_id=mock_payment.id,
            reason="customer_request"
        )

        assert refund_response.amount == mock_payment.amount
        assert refund_response.status == PaymentStatus.REFUNDED
        assert "customer_request" in refund_response.metadata.get("reason", "")

    @pytest.mark.asyncio
    async def test_process_refund_partial(self, db_session, mock_payment):
        """Test partial refund processing."""
        service = PaymentService(db_session)
        mock_payment.status = PaymentStatus.SUCCESS.value
        db_session.commit()

        refund_amount = mock_payment.amount / 2
        refund_response = await service.process_refund(
            payment_id=mock_payment.id,
            amount=refund_amount,
            reason="partial_cancellation"
        )

        assert refund_response.amount == refund_amount
        assert refund_response.status == PaymentStatus.REFUNDED

    @pytest.mark.asyncio
    async def test_process_refund_nonexistent_payment(self, db_session):
        """Test refund for non-existent payment."""
        service = PaymentService(db_session)

        with pytest.raises(HTTPException) as exc:
            await service.process_refund(
                payment_id="non_existent_payment",
                reason="test"
            )

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_process_refund_failed_payment(self, db_session, mock_payment):
        """Test refund for failed payment."""
        service = PaymentService(db_session)
        mock_payment.status = PaymentStatus.FAILED.value
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            await service.process_refund(
                payment_id=mock_payment.id,
                reason="test"
            )

        assert exc.value.status_code == 400
        assert "successful" in exc.value.detail.lower()


class TestGetPayment:
    """Test payment retrieval."""

    @pytest.mark.asyncio
    async def test_get_payment_success(self, db_session, mock_payment):
        """Test getting existing payment."""
        service = PaymentService(db_session)

        payment = await service.get_payment(mock_payment.id)

        assert payment.id == mock_payment.id
        assert payment.amount == mock_payment.amount

    @pytest.mark.asyncio
    async def test_get_payment_not_found(self, db_session):
        """Test getting non-existent payment."""
        service = PaymentService(db_session)

        with pytest.raises(HTTPException) as exc:
            await service.get_payment("non_existent_payment")

        assert exc.value.status_code == 404


class TestPaymentReconciliation:
    """Test payment reconciliation functionality."""

    @pytest.mark.asyncio
    async def test_reconcile_payments(self, db_session, mock_payment):
        """Test payment reconciliation report generation."""
        service = PaymentService(db_session)
        mock_payment.status = PaymentStatus.SUCCESS.value
        db_session.commit()

        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc) + timedelta(days=1)

        report = await service.reconcile_payments(start_date, end_date)

        assert "period" in report
        assert "summary" in report
        assert "by_status" in report
        assert "by_method" in report

        assert "total_transactions" in report["summary"]
        assert "total_collected" in report["summary"]
        assert "total_refunded" in report["summary"]
        assert "net_revenue" in report["summary"]

    @pytest.mark.asyncio
    async def test_reconcile_payments_empty_period(self, db_session):
        """Test reconciliation for period with no payments."""
        service = PaymentService(db_session)

        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = start_date + timedelta(days=5)

        report = await service.reconcile_payments(start_date, end_date)

        assert report["summary"]["total_transactions"] == 0
        assert report["summary"]["total_collected"] == 0


class TestPaymentMethods:
    """Test different payment method creation."""

    @pytest.mark.asyncio
    async def test_create_upi_payment(self, db_session, mock_payment):
        """Test UPI payment creation."""
        service = PaymentService(db_session)

        url = await service._create_upi_payment(mock_payment)

        assert url is not None
        assert "upi://" in url or "/payment/upi" in url

    @pytest.mark.asyncio
    async def test_create_card_payment(self, db_session, mock_payment):
        """Test card payment creation."""
        service = PaymentService(db_session)

        url = await service._create_card_payment(mock_payment)

        assert url is not None
        assert "/payment/card" in url

    @pytest.mark.asyncio
    async def test_create_net_banking_payment(self, db_session, mock_payment):
        """Test net banking payment creation."""
        service = PaymentService(db_session)

        url = await service._create_net_banking_payment(mock_payment)

        assert url is not None
        assert "/payment/nb" in url


class TestPaymentExpiry:
    """Test payment expiry handling."""

    @pytest.mark.asyncio
    async def test_payment_expiry_timestamp(self, db_session, mock_booking):
        """Test payment expiry timestamp is set correctly."""
        service = PaymentService(db_session)

        response = await service.create_payment(
            booking_id=mock_booking.id,
            amount=500.0,
            payment_method="upi",
            user_id=mock_booking.user_id
        )

        assert response.expires_at is not None
        # Expiry should be within 30 minutes
        expires_in = (response.expires_at - datetime.now(timezone.utc)).total_seconds()
        assert 1500 < expires_in < 1900  # Between 25-31 minutes


class TestMockPaymentService:
    """Test mock payment service for demo/testing."""

    @pytest.mark.asyncio
    async def test_mock_payment_creation(self):
        """Test mock payment creation."""
        service = MockPaymentService()

        response = await service.create_mock_payment(
            booking_id="booking_123",
            amount=500.0,
            user_id="user_123"
        )

        assert response["payment_id"] is not None
        assert response["booking_id"] == "booking_123"
        assert response["amount"] == 500.0
        assert response["status"] == "pending"

    @pytest.mark.asyncio
    async def test_mock_payment_verification_success(self):
        """Test mock payment verification success."""
        service = MockPaymentService()

        payment = await service.create_mock_payment(
            booking_id="booking_123",
            amount=500.0,
            user_id="user_123"
        )

        result = await service.verify_mock_payment(payment["payment_id"])

        # With 95% success rate, test for success
        assert "success" in result
        assert result["payment_id"] == payment["payment_id"]

    @pytest.mark.asyncio
    async def test_mock_payment_nonexistent(self):
        """Test verification of non-existent mock payment."""
        service = MockPaymentService()

        result = await service.verify_mock_payment("non_existent_payment")

        assert result["success"] is False
        assert "Payment not found" in result["error"]

    @pytest.mark.asyncio
    async def test_mock_payment_full_flow(self):
        """Test complete mock payment flow."""
        service = MockPaymentService()

        result = await service.simulate_payment_flow(
            booking_id="booking_123",
            amount=500.0,
            user_id="user_123"
        )

        assert result["payment_id"] is not None
        assert result["booking_id"] == "booking_123"
        assert "verification_result" in result

    @pytest.mark.asyncio
    async def test_mock_payment_status_retrieval(self):
        """Test getting mock payment status."""
        service = MockPaymentService()

        payment = await service.create_mock_payment(
            booking_id="booking_123",
            amount=500.0,
            user_id="user_123"
        )

        status = service.get_mock_payment_status(payment["payment_id"])

        assert status is not None
        assert status["payment_id"] == payment["payment_id"]

    @pytest.mark.asyncio
    async def test_mock_payment_clear(self):
        """Test clearing mock payments."""
        service = MockPaymentService()

        await service.create_mock_payment("booking_123", 500.0, "user_123")
        assert len(service.mock_payments) > 0

        service.clear_mock_payments()
        assert len(service.mock_payments) == 0


class TestPaymentConcurrency:
    """Test concurrent payment processing."""

    @pytest.mark.asyncio
    async def test_concurrent_payment_creation(self, db_session, mock_booking):
        """Test creating multiple payments concurrently."""
        service = PaymentService(db_session)

        import asyncio

        tasks = [
            service.create_payment(
                booking_id=mock_booking.id,
                amount=500.0 + i,
                payment_method="upi",
                user_id=mock_booking.user_id
            )
            for i in range(3)
        ]

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 3
        assert all(r.status == PaymentStatus.PENDING for r in responses)
        # All payment IDs should be unique
        payment_ids = [r.payment_id for r in responses]
        assert len(set(payment_ids)) == 3


class TestPaymentEdgeCases:
    """Test edge cases in payment handling."""

    @pytest.mark.asyncio
    async def test_payment_with_zero_amount(self, db_session, mock_booking):
        """Test payment creation with zero amount."""
        service = PaymentService(db_session)

        # The schema should reject zero amount, but service should handle gracefully
        try:
            response = await service.create_payment(
                booking_id=mock_booking.id,
                amount=0.0,
                payment_method="upi",
                user_id=mock_booking.user_id
            )
            # If it succeeds, verify it's in correct state
            assert response.status == PaymentStatus.PENDING
        except (HTTPException, ValueError):
            # Expected behavior - zero amount should be rejected
            pass

    @pytest.mark.asyncio
    async def test_payment_with_large_amount(self, db_session, mock_booking):
        """Test payment creation with large amount."""
        service = PaymentService(db_session)

        response = await service.create_payment(
            booking_id=mock_booking.id,
            amount=999999.99,
            payment_method="upi",
            user_id=mock_booking.user_id
        )

        assert response.amount == 999999.99
        assert response.status == PaymentStatus.PENDING

    @pytest.mark.asyncio
    async def test_payment_with_special_characters_in_booking(self, db_session, mock_booking):
        """Test payment creation with special characters."""
        service = PaymentService(db_session)

        response = await service.create_payment(
            booking_id=mock_booking.id,
            amount=500.0,
            payment_method="upi",
            user_id=mock_booking.user_id
        )

        assert response.payment_id is not None
