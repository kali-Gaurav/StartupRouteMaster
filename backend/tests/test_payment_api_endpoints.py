from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import sessionmaker
from backend.app import app
from backend.api.dependencies import get_current_user
from backend.database.models import User, Booking, Payment


@pytest.fixture(scope="function")
def auth_client(test_engine, test_session):
    # create a dummy user and override get_current_user dependency
    user = User(id="user-1", email="user@example.com")
    test_session.add(user)
    test_session.commit()

    def _override_current_user():
        return user

    app.dependency_overrides[get_current_user] = _override_current_user

    with TestClient(app) as client:
        yield client, user

    app.dependency_overrides.clear()


def create_booking_and_payment(test_session, user, route_id="route-123", travel_date="2026-03-01", status="pending"):
    # create booking
    booking = Booking(
        id="bk-1",
        pnr_number="PNR123",
        user_id=user.id,
        travel_date=travel_date,
        booking_status="pending",
        amount_paid=100.0,
        booking_details={}
    )
    test_session.add(booking)
    test_session.flush()
    payment = Payment(
        id="pm-1",
        booking_id=booking.id,
        razorpay_order_id="order-xyz",
        status=status,
        amount=100.0,
    )
    test_session.add(payment)
    test_session.commit()
    return booking, payment


def test_payment_status_endpoint(auth_client, test_session):
    client, user = auth_client
    # create booking/payment with completed status
    _, payment = create_booking_and_payment(test_session, user, status="completed")

    resp = client.get(f"/api/payments/status/{payment.razorpay_order_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_id"] == payment.razorpay_order_id
    assert data["status"] == "completed"


def test_payment_history_pagination(auth_client, test_session):
    client, user = auth_client
    # create two payments
    create_booking_and_payment(test_session, user, route_id="route-1", travel_date="2026-03-01", status="completed")
    create_booking_and_payment(test_session, user, route_id="route-2", travel_date="2026-03-02", status="pending")

    # request with limit=1
    resp = client.get("/api/payments/booking/history?skip=0&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["total"] >= 2
    assert len(data["payments"]) == 1
    assert data["skip"] == 0
    assert data["limit"] == 1


def test_check_payment_status_endpoint(auth_client, test_session):
    client, user = auth_client
    booking, payment = create_booking_and_payment(test_session, user, route_id="route-abc", travel_date="2026-04-01", status="completed")

    resp = client.get("/api/payments/check_payment_status", params={
        "route_id": booking.route_id,
        "travel_date": booking.travel_date,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["paid"] is True
    assert data.get("already_paid_booking") is True
