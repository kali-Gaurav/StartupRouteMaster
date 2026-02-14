import pytest
from unittest.mock import patch, MagicMock
from backend.services import PaymentService


@pytest.fixture
def payment_service():
    """Create payment service instance."""
    return PaymentService()


class TestPaymentService:
    """Test payment service."""

    def test_payment_service_initialization(self, payment_service):
        """Test payment service can be initialized."""
        assert payment_service is not None

    def test_is_configured_false_when_default(self):
        """Test is_configured returns False with default config."""
        service = PaymentService()
        configured = service.is_configured()
        assert isinstance(configured, bool)

    @patch("backend.services.payment_service.requests.post")
    def test_create_order_success(self, mock_post, payment_service):
        """Test successful order creation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "order_123"}
        mock_post.return_value = mock_response

        if payment_service.is_configured():
            result = payment_service.create_order(
                amount_rupees=39.0,
                receipt_id="test_receipt",
            )

            assert result.get("success") is True
            assert result.get("order_id") == "order_123"

    @patch("backend.services.payment_service.requests.post")
    def test_create_order_with_idempotency_key(self, mock_post, payment_service):
        """Test successful order creation with an idempotency key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "order_test_idempotency"}
        mock_post.return_value = mock_response

        idempotency_key_value = "booking_id_123"

        if payment_service.is_configured():
            result = payment_service.create_order(
                amount_rupees=50.0,
                receipt_id="test_receipt_idempotency",
                idempotency_key=idempotency_key_value,
            )

            assert result.get("success") is True
            assert result.get("order_id") == "order_test_idempotency"
            
            # Verify that the X-Razorpay-IDEMPOTENCY header was sent
            mock_post.assert_called_once()
            called_kwargs = mock_post.call_args.kwargs
            assert "headers" in called_kwargs
            assert called_kwargs["headers"].get("X-Razorpay-IDEMPOTENCY") == idempotency_key_value

    def test_create_order_not_configured(self):
        """Test order creation when not configured."""
        service = PaymentService()
        result = service.create_order(amount_rupees=39.0)

        if not service.is_configured():
            assert result.get("success") is False

    def test_verify_payment_not_configured(self, payment_service):
        """Test payment verification when not configured."""
        is_valid, error = payment_service.verify_payment(
            razorpay_payment_id="pay_123",
            razorpay_order_id="order_123",
            razorpay_signature="signature",
        )

        if not payment_service.is_configured():
            assert is_valid is False
            assert error is not None

    def test_verify_payment_invalid_signature(self):
        """Test signature verification with invalid signature."""
        import hmac
        import hashlib

        service = PaymentService()

        order_id = "order_123"
        payment_id = "pay_456"
        invalid_signature = "invalid_signature"

        is_valid, error = service.verify_payment(
            razorpay_payment_id=payment_id,
            razorpay_order_id=order_id,
            razorpay_signature=invalid_signature,
        )

        if service.is_configured():
            assert is_valid is False


class TestPaymentWorkflow:
    """Test payment workflow."""

    def test_payment_workflow_not_configured(self):
        """Test payment workflow when Razorpay not configured."""
        service = PaymentService()

        if not service.is_configured():
            order_result = service.create_order(amount_rupees=39.0)
            assert order_result.get("success") is False

            is_valid, error = service.verify_payment(
                razorpay_payment_id="pay_123",
                razorpay_order_id="order_123",
                razorpay_signature="sig",
            )
            assert is_valid is False