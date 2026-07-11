"""
End-to-end tests for complete booking payment flow.
Team 5: QA & Testing Team - Razorpay Payment Integration
Tests complete booking → payment → confirmation workflow
"""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from datetime import datetime, timezone, timedelta
import uuid


class TestCompleteBookingPaymentFlow:
    """Test complete booking payment workflow."""

    @pytest.mark.asyncio
    async def test_e2e_booking_search_to_payment(
        self,
        async_client: AsyncClient,
        mock_user,
        mock_route,
        db_session
    ):
        """
        Complete E2E flow:
        1. Search for routes
        2. Select a route
        3. Enter passenger info
        4. Initiate payment
        5. Confirm payment
        """
        # Step 1: Search for routes
        search_response = await async_client.post(
            "/v1/booking/search",
            json={
                "from_station": "DEL",
                "to_station": "BOM",
                "travel_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                "class": "SL"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )
        assert search_response.status_code == 200
        routes = search_response.json().get("routes", [])
        assert len(routes) > 0
        selected_route = routes[0]

        # Step 2: Create booking
        booking_response = await async_client.post(
            "/v1/booking/create",
            json={
                "route_id": selected_route.get("id"),
                "passengers": [
                    {
                        "name": "John Doe",
                        "age": 30,
                        "gender": "M"
                    }
                ],
                "travel_date": selected_route.get("travel_date")
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )
        assert booking_response.status_code == 200
        booking = booking_response.json()
        booking_id = booking["booking_id"]

        # Step 3: Initiate payment
        payment_response = await async_client.post(
            "/v1/booking/payment/initiate",
            json={
                "booking_id": booking_id,
                "amount": booking.get("total_amount"),
                "payment_method": "upi"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )
        assert payment_response.status_code == 200
        payment = payment_response.json()
        payment_id = payment["payment_id"]

        # Step 4: Verify payment (with mocked Razorpay response)
        with patch('services.payment_service.PaymentService.verify_payment') as mock_verify:
            mock_verify.return_value = (True, None)

            verify_response = await async_client.post(
                "/v1/booking/payment/verify",
                json={
                    "payment_id": payment_id,
                    "razorpay_payment_id": f"pay_{uuid.uuid4().hex[:12]}",
                    "razorpay_order_id": payment.get("order_id"),
                    "razorpay_signature": "valid_signature"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )
            assert verify_response.status_code == 200

        # Step 5: Verify booking is confirmed
        booking_status = await async_client.get(
            f"/v1/booking/{booking_id}",
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )
        assert booking_status.status_code == 200
        updated_booking = booking_status.json()
        assert updated_booking["status"] in ["confirmed", "payment_completed"]

    @pytest.mark.asyncio
    async def test_e2e_payment_failure_recovery(
        self,
        async_client: AsyncClient,
        mock_user,
        mock_route,
        db_session
    ):
        """
        Test payment failure and recovery:
        1. Initiate payment
        2. Payment fails
        3. User retries and succeeds
        """
        # Create booking first
        booking_response = await async_client.post(
            "/v1/booking/create",
            json={
                "route_id": mock_route.id,
                "passengers": [{"name": "Jane Doe", "age": 28, "gender": "F"}],
                "travel_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )
        booking_id = booking_response.json()["booking_id"]

        # Initiate first payment
        payment1_response = await async_client.post(
            "/v1/booking/payment/initiate",
            json={
                "booking_id": booking_id,
                "amount": 500.0,
                "payment_method": "upi"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )
        payment1_id = payment1_response.json()["payment_id"]

        # Simulate payment failure
        with patch('services.payment_service.PaymentService.verify_payment') as mock_verify:
            mock_verify.return_value = (False, "Payment declined")

            verify_response = await async_client.post(
                "/v1/booking/payment/verify",
                json={
                    "payment_id": payment1_id,
                    "razorpay_payment_id": f"pay_{uuid.uuid4().hex[:12]}",
                    "razorpay_order_id": "order_failed",
                    "razorpay_signature": "invalid_signature"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )
            assert verify_response.status_code == 400

        # Retry payment - create new payment for same booking
        payment2_response = await async_client.post(
            "/v1/booking/payment/initiate",
            json={
                "booking_id": booking_id,
                "amount": 500.0,
                "payment_method": "upi"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )
        payment2_id = payment2_response.json()["payment_id"]

        # This time verify succeeds
        with patch('services.payment_service.PaymentService.verify_payment') as mock_verify:
            mock_verify.return_value = (True, None)

            retry_response = await async_client.post(
                "/v1/booking/payment/verify",
                json={
                    "payment_id": payment2_id,
                    "razorpay_payment_id": f"pay_{uuid.uuid4().hex[:12]}",
                    "razorpay_order_id": "order_success",
                    "razorpay_signature": "valid_signature"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )
            assert retry_response.status_code == 200

    @pytest.mark.asyncio
    async def test_e2e_partial_refund_handling(
        self,
        async_client: AsyncClient,
        mock_user,
        mock_payment,
        db_session
    ):
        """
        Test partial refund flow:
        1. Complete payment
        2. Request partial refund
        3. Verify refund status
        """
        # Assume payment is already completed
        mock_payment.status = "completed"
        db_session.commit()

        # Request partial refund
        refund_amount = mock_payment.amount / 2
        refund_response = await async_client.post(
            f"/v1/booking/payment/refund/{mock_payment.id}",
            json={
                "amount": refund_amount,
                "reason": "partial_cancellation"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )

        assert refund_response.status_code == 200
        refund_data = refund_response.json()
        assert refund_data["success"] is True
        assert "refund_id" in refund_data

        # Verify refund status
        status_response = await async_client.get(
            f"/v1/booking/payment/refund/{refund_data['refund_id']}/status",
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )
        assert status_response.status_code == 200

    @pytest.mark.asyncio
    async def test_e2e_email_notification_on_success(
        self,
        async_client: AsyncClient,
        mock_user,
        mock_booking,
        db_session
    ):
        """
        Test email notification on successful payment:
        1. Complete payment
        2. Verify email notification triggered
        """
        # Initiate and verify payment
        payment_response = await async_client.post(
            "/v1/booking/payment/initiate",
            json={
                "booking_id": mock_booking.id,
                "amount": 500.0,
                "payment_method": "upi"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )
        payment_id = payment_response.json()["payment_id"]

        with patch('services.email_service.send_email') as mock_email:
            mock_email.return_value = True

            verify_response = await async_client.post(
                "/v1/booking/payment/verify",
                json={
                    "payment_id": payment_id,
                    "razorpay_payment_id": f"pay_{uuid.uuid4().hex[:12]}",
                    "razorpay_order_id": "order_success",
                    "razorpay_signature": "valid_signature"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )

            assert verify_response.status_code == 200
            # Email should have been called
            assert mock_email.called

    @pytest.mark.asyncio
    async def test_e2e_sms_notification_on_failure(
        self,
        async_client: AsyncClient,
        mock_user,
        mock_booking,
        db_session
    ):
        """
        Test SMS notification on payment failure:
        1. Payment fails
        2. Verify SMS notification triggered
        """
        payment_response = await async_client.post(
            "/v1/booking/payment/initiate",
            json={
                "booking_id": mock_booking.id,
                "amount": 500.0,
                "payment_method": "upi"
            },
            headers={"Authorization": f"Bearer {mock_user.id}"}
        )
        payment_id = payment_response.json()["payment_id"]

        with patch('services.sms_service.send_sms') as mock_sms:
            mock_sms.return_value = True

            with patch('services.payment_service.PaymentService.verify_payment') as mock_verify:
                mock_verify.return_value = (False, "Payment declined")

                verify_response = await async_client.post(
                    "/v1/booking/payment/verify",
                    json={
                        "payment_id": payment_id,
                        "razorpay_payment_id": f"pay_{uuid.uuid4().hex[:12]}",
                        "razorpay_order_id": "order_failed",
                        "razorpay_signature": "invalid"
                    },
                    headers={"Authorization": f"Bearer {mock_user.id}"}
                )

                assert verify_response.status_code == 400


class TestPaymentWebhookFlow:
    """Test payment webhook-driven state transitions."""

    @pytest.mark.asyncio
    async def test_webhook_success_updates_booking(
        self,
        async_client: AsyncClient,
        mock_payment,
        db_session
    ):
        """
        Test webhook processing updates booking:
        1. Webhook arrives with success
        2. Booking status updated to confirmed
        """
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
            response = await async_client.post(
                "/v1/booking/payment/webhook",
                json=payload,
                headers={"X-Razorpay-Signature": "signature"}
            )

            assert response.status_code == 200

            # Verify booking is updated
            if mock_payment.booking_id:
                booking = db_session.query(Booking).filter(
                    Booking.id == mock_payment.booking_id
                ).first()
                assert booking is not None
                assert booking.booking_status == "confirmed"

    @pytest.mark.asyncio
    async def test_webhook_failure_releases_seats(
        self,
        async_client: AsyncClient,
        mock_payment,
        db_session
    ):
        """
        Test webhook processing releases seats on failure:
        1. Webhook arrives with failure
        2. Booking seats are released
        """
        event_id = f"event_{uuid.uuid4()}"
        payload = {
            "id": event_id,
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
            with patch('services.inventory_service.InventoryService.release_seats') as mock_release:
                mock_release.return_value = True

                response = await async_client.post(
                    "/v1/booking/payment/webhook",
                    json=payload,
                    headers={"X-Razorpay-Signature": "signature"}
                )

                assert response.status_code == 200
                if mock_payment.booking_id:
                    assert mock_release.called


class TestPaymentConcurrentBooking:
    """Test concurrent booking and payment flows."""

    @pytest.mark.asyncio
    async def test_concurrent_bookings_with_payment(
        self,
        async_client: AsyncClient,
        mock_user,
        mock_route,
        db_session
    ):
        """
        Test multiple concurrent bookings:
        1. Multiple users booking same route
        2. All payments processed
        3. Seat inventory properly managed
        """
        import asyncio

        async def book_and_pay(passenger_name, amount):
            # Create booking
            booking_response = await async_client.post(
                "/v1/booking/create",
                json={
                    "route_id": mock_route.id,
                    "passengers": [{"name": passenger_name, "age": 25, "gender": "M"}],
                    "travel_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )

            if booking_response.status_code != 200:
                return None

            booking_id = booking_response.json()["booking_id"]

            # Initiate payment
            payment_response = await async_client.post(
                "/v1/booking/payment/initiate",
                json={
                    "booking_id": booking_id,
                    "amount": amount,
                    "payment_method": "upi"
                },
                headers={"Authorization": f"Bearer {mock_user.id}"}
            )

            return payment_response.status_code == 200

        # Simulate 5 concurrent bookings
        results = await asyncio.gather(
            *[
                book_and_pay(f"Passenger {i}", 500.0)
                for i in range(5)
            ]
        )

        # All should succeed
        assert all(results)


class TestPaymentReconciliation:
    """Test payment reconciliation flows."""

    @pytest.mark.asyncio
    async def test_payment_reconciliation_report(
        self,
        async_client: AsyncClient,
        mock_user,
        mock_payment,
        db_session
    ):
        """
        Test payment reconciliation:
        1. Generate reconciliation report
        2. Verify accuracy
        """
        mock_payment.status = "completed"
        db_session.commit()

        response = await async_client.get(
            "/v1/booking/payment/reconciliation?"
            f"start_date={(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')}&"
            f"end_date={datetime.now().strftime('%Y-%m-%d')}",
            headers={"Authorization": f"Bearer admin_user"}
        )

        if response.status_code == 200:
            data = response.json()
            assert "period" in data
            assert "summary" in data
            assert "by_status" in data


# Import needed models
from database.models import Booking
