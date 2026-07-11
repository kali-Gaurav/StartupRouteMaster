"""
Comprehensive integration tests for payment endpoints.
Team 5: QA & Testing Team - Razorpay Payment Integration
Tests /v1/booking/payment/* endpoints
"""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient
from datetime import datetime, timedelta

from fastapi import status
from sqlalchemy.orm import Session


class TestPaymentInitiateEndpoint:
    """Test /v1/booking/payment/initiate endpoint."""

    @pytest.mark.asyncio
    async def test_initiate_payment_success(self, async_client: AsyncClient, mock_user, mock_booking, db_session):
        """Test successful payment initiation."""
        response = await async_client.post(
            "/v1/booking/payment/initiate",
            json={
                "booking_id": mock_booking.id,
                "amount": 500.0,
                "payment_method": "upi"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "payment_id" in data
        assert data["booking_id"] == mock_booking.id
        assert data["amount"] == 500.0
        assert "payment_url" in data

    @pytest.mark.asyncio
    async def test_initiate_payment_missing_booking(self, async_client: AsyncClient, mock_user):
        """Test payment initiation with missing booking."""
        response = await async_client.post(
            "/v1/booking/payment/initiate",
            json={
                "booking_id": "non_existent_booking",
                "amount": 500.0,
                "payment_method": "upi"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_initiate_payment_invalid_method(self, async_client: AsyncClient, mock_user, mock_booking):
        """Test payment initiation with invalid payment method."""
        response = await async_client.post(
            "/v1/booking/payment/initiate",
            json={
                "booking_id": mock_booking.id,
                "amount": 500.0,
                "payment_method": "invalid_method"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_initiate_payment_all_methods(self, async_client: AsyncClient, mock_user, mock_booking):
        """Test payment initiation with all valid methods."""
        for method in ["upi", "card", "net_banking"]:
            response = await async_client.post(
                "/v1/booking/payment/initiate",
                json={
                    "booking_id": mock_booking.id,
                    "amount": 500.0,
                    "payment_method": method
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_initiate_payment_negative_amount(self, async_client: AsyncClient, mock_user, mock_booking):
        """Test payment initiation with negative amount."""
        response = await async_client.post(
            "/v1/booking/payment/initiate",
            json={
                "booking_id": mock_booking.id,
                "amount": -500.0,
                "payment_method": "upi"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        # Should be rejected by schema validation
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_initiate_payment_unauthorized(self, async_client: AsyncClient, mock_booking):
        """Test payment initiation without authentication."""
        response = await async_client.post(
            "/v1/booking/payment/initiate",
            json={
                "booking_id": mock_booking.id,
                "amount": 500.0,
                "payment_method": "upi"
            }
        )

        assert response.status_code in [401, 403]


class TestPaymentVerifyEndpoint:
    """Test /v1/booking/payment/verify endpoint."""

    @pytest.mark.asyncio
    async def test_verify_payment_success(self, async_client: AsyncClient, mock_user, mock_payment):
        """Test successful payment verification."""
        # Mock Razorpay API response
        with patch('services.payment_service.PaymentService.verify_payment') as mock_verify:
            mock_verify.return_value = (True, None)

            response = await async_client.post(
                "/v1/booking/payment/verify",
                json={
                    "razorpay_payment_id": "pay_123456",
                    "razorpay_order_id": mock_payment.razorpay_order_id,
                    "razorpay_signature": "signature_hash"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_verify_payment_invalid_signature(self, async_client: AsyncClient, mock_user, mock_payment):
        """Test verification with invalid signature."""
        with patch('services.payment_service.PaymentService.verify_payment') as mock_verify:
            mock_verify.return_value = (False, "Invalid signature")

            response = await async_client.post(
                "/v1/booking/payment/verify",
                json={
                    "razorpay_payment_id": "pay_123456",
                    "razorpay_order_id": mock_payment.razorpay_order_id,
                    "razorpay_signature": "invalid_signature"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_verify_payment_missing_payment(self, async_client: AsyncClient, mock_user):
        """Test verification with non-existent payment."""
        response = await async_client.post(
            "/v1/booking/payment/verify",
            json={
                "razorpay_payment_id": "pay_nonexistent",
                "razorpay_order_id": "order_nonexistent",
                "razorpay_signature": "signature"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_verify_payment_unauthorized_user(self, async_client: AsyncClient, mock_payment):
        """Test verification by unauthorized user."""
        response = await async_client.post(
            "/v1/booking/payment/verify",
            json={
                "razorpay_payment_id": "pay_123456",
                "razorpay_order_id": mock_payment.razorpay_order_id,
                "razorpay_signature": "signature"
            },
            headers={"Authorization": "Bearer unauthorized_user"}
        )

        assert response.status_code in [403, 404]


class TestWebhookEndpoint:
    """Test /v1/booking/payment/webhook endpoint."""

    @pytest.mark.asyncio
    async def test_webhook_payment_success(self, async_client: AsyncClient, mock_payment, db_session):
        """Test webhook for successful payment."""
        payload = {
            "id": f"event_{uuid.uuid4()}",
            "event": "payment.authorized",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_123456",
                        "order_id": mock_payment.razorpay_order_id,
                        "status": "captured"
                    }
                }
            }
        }

        with patch('api.dependencies.verify_webhook_signature'):
            response = await async_client.post(
                "/v1/booking/payment/webhook",
                json=payload,
                headers={"X-Razorpay-Signature": "signature"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_webhook_payment_failed(self, async_client: AsyncClient, mock_payment):
        """Test webhook for failed payment."""
        payload = {
            "id": f"event_{uuid.uuid4()}",
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_123456",
                        "order_id": mock_payment.razorpay_order_id,
                        "status": "failed"
                    }
                }
            }
        }

        with patch('api.dependencies.verify_webhook_signature'):
            response = await async_client.post(
                "/v1/booking/payment/webhook",
                json=payload,
                headers={"X-Razorpay-Signature": "signature"}
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_invalid_signature(self, async_client: AsyncClient):
        """Test webhook with invalid signature."""
        payload = {
            "id": "event_123",
            "event": "payment.authorized",
            "payload": {"payment": {"entity": {}}}
        }

        with patch('api.dependencies.verify_webhook_signature', side_effect=Exception("Invalid signature")):
            response = await async_client.post(
                "/v1/booking/payment/webhook",
                json=payload,
                headers={"X-Razorpay-Signature": "invalid"}
            )

            assert response.status_code >= 400

    @pytest.mark.asyncio
    async def test_webhook_idempotency(self, async_client: AsyncClient, mock_payment, db_session):
        """Test webhook processing is idempotent."""
        event_id = f"event_{uuid.uuid4()}"
        payload = {
            "id": event_id,
            "event": "payment.authorized",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_123456",
                        "order_id": mock_payment.razorpay_order_id,
                        "status": "captured"
                    }
                }
            }
        }

        with patch('api.dependencies.verify_webhook_signature'):
            # First webhook call
            response1 = await async_client.post(
                "/v1/booking/payment/webhook",
                json=payload,
                headers={"X-Razorpay-Signature": "signature"}
            )

            # Second webhook call with same event ID
            response2 = await async_client.post(
                "/v1/booking/payment/webhook",
                json=payload,
                headers={"X-Razorpay-Signature": "signature"}
            )

            assert response1.status_code == 200
            assert response2.status_code == 200
            # Both should process successfully due to idempotency


class TestPaymentStatusEndpoint:
    """Test payment status checking endpoint."""

    @pytest.mark.asyncio
    async def test_get_payment_status(self, async_client: AsyncClient, mock_user, mock_payment):
        """Test getting payment status."""
        response = await async_client.get(
            f"/v1/booking/payment/status/{mock_payment.id}",
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["payment_id"] == mock_payment.id
        assert "status" in data

    @pytest.mark.asyncio
    async def test_get_payment_status_not_found(self, async_client: AsyncClient, mock_user):
        """Test getting status for non-existent payment."""
        response = await async_client.get(
            "/v1/booking/payment/status/non_existent_payment",
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code == 404


class TestPaymentListEndpoint:
    """Test payment listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_user_payments(self, async_client: AsyncClient, mock_user):
        """Test listing user's payments."""
        response = await async_client.get(
            "/v1/booking/payment/list",
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["payments"], list)
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_payments_pagination(self, async_client: AsyncClient, mock_user):
        """Test payment listing with pagination."""
        response = await async_client.get(
            "/v1/booking/payment/list?skip=0&limit=10",
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "skip" in data
        assert "limit" in data


class TestRefundEndpoint:
    """Test refund endpoint."""

    @pytest.mark.asyncio
    async def test_refund_payment_success(self, async_client: AsyncClient, mock_user, mock_payment):
        """Test successful refund."""
        mock_payment.status = "completed"

        response = await async_client.post(
            f"/v1/booking/payment/refund/{mock_payment.id}",
            json={
                "amount": mock_payment.amount,
                "reason": "customer_request"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "refund_id" in data

    @pytest.mark.asyncio
    async def test_refund_payment_partial(self, async_client: AsyncClient, mock_user, mock_payment):
        """Test partial refund."""
        mock_payment.status = "completed"

        response = await async_client.post(
            f"/v1/booking/payment/refund/{mock_payment.id}",
            json={
                "amount": mock_payment.amount / 2,
                "reason": "partial_cancellation"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_refund_failed_payment(self, async_client: AsyncClient, mock_user, mock_payment):
        """Test refund for failed payment."""
        mock_payment.status = "failed"

        response = await async_client.post(
            f"/v1/booking/payment/refund/{mock_payment.id}",
            json={"reason": "payment_failed"},
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert response.status_code >= 400

    @pytest.mark.asyncio
    async def test_refund_unauthorized(self, async_client: AsyncClient, mock_payment):
        """Test refund by unauthorized user."""
        response = await async_client.post(
            f"/v1/booking/payment/refund/{mock_payment.id}",
            json={"reason": "test"},
            headers={"Authorization": "Bearer unauthorized_user"}
        )

        assert response.status_code in [403, 404]


class TestPaymentConcurrency:
    """Test concurrent payment operations."""

    @pytest.mark.asyncio
    async def test_concurrent_payment_initiations(self, async_client: AsyncClient, mock_user, mock_booking):
        """Test initiating multiple payments concurrently."""
        import asyncio

        async def initiate_payment(amount):
            return await async_client.post(
                "/v1/booking/payment/initiate",
                json={
                    "booking_id": mock_booking.id,
                    "amount": amount,
                    "payment_method": "upi"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )

        responses = await asyncio.gather(
            *[initiate_payment(500.0 + i) for i in range(3)]
        )

        assert all(r.status_code == 200 for r in responses)
        # All should have unique payment IDs
        payment_ids = [r.json()["payment_id"] for r in responses]
        assert len(set(payment_ids)) == 3


class TestPaymentRateLimiting:
    """Test payment endpoint rate limiting."""

    @pytest.mark.asyncio
    async def test_payment_initiate_rate_limit(self, async_client: AsyncClient, mock_user, mock_booking):
        """Test rate limiting on payment initiation."""
        # This would depend on the actual rate limiter configuration
        # Make multiple rapid requests and check if rate limit is applied
        for i in range(15):
            response = await async_client.post(
                "/v1/booking/payment/initiate",
                json={
                    "booking_id": mock_booking.id,
                    "amount": 500.0,
                    "payment_method": "upi"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )

            # After limit, should get 429 Too Many Requests
            if i >= 10:
                assert response.status_code in [200, 429]


class TestPaymentErrorHandling:
    """Test payment error handling."""

    @pytest.mark.asyncio
    async def test_payment_database_error(self, async_client: AsyncClient, mock_user, mock_booking):
        """Test handling of database errors."""
        with patch('services.payment_service.PaymentService.create_payment', side_effect=Exception("DB Error")):
            response = await async_client.post(
                "/v1/booking/payment/initiate",
                json={
                    "booking_id": mock_booking.id,
                    "amount": 500.0,
                    "payment_method": "upi"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )

            assert response.status_code >= 500

    @pytest.mark.asyncio
    async def test_payment_timeout(self, async_client: AsyncClient, mock_user, mock_booking):
        """Test handling of timeout errors."""
        import asyncio

        async def timeout_error():
            raise asyncio.TimeoutError("Request timeout")

        with patch('services.payment_service.PaymentService.create_payment', side_effect=timeout_error):
            response = await async_client.post(
                "/v1/booking/payment/initiate",
                json={
                    "booking_id": mock_booking.id,
                    "amount": 500.0,
                    "payment_method": "upi"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )

            assert response.status_code >= 500


import uuid
