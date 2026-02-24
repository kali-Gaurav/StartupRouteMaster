from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import sessionmaker
from backend.app import app
from backend.api.dependencies import get_current_user
from backend.database.models import User, Booking, Payment


@pytest.fixture(scope="function")
def auth_client(db_session):
    # create a dummy user and override get_current_user dependency
    import uuid
    user = User(id=str(uuid.uuid4()), email=f"user+{uuid.uuid4()}@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    def _override_current_user():
        return user

    app.dependency_overrides[get_current_user] = _override_current_user

    # override webhook verification to bypass signature checking during tests
    from backend.api.dependencies import verify_webhook_signature

    app.dependency_overrides[verify_webhook_signature] = lambda request: None
    with TestClient(app) as client:
        yield client, user

    app.dependency_overrides.clear()


import uuid
from datetime import datetime, date


def create_booking_and_payment(db_session, user, route_id="route-123", travel_date="2026-03-01", status="pending"):
    # ensure travel_date is a date object (SQLAlchemy Date expects that)
    if isinstance(travel_date, str):
        travel_date = datetime.fromisoformat(travel_date).date()

    # create booking with unique identifiers
    booking = Booking(
        id=str(uuid.uuid4()),
        pnr_number=str(uuid.uuid4())[:10],
        user_id=user.id,
        travel_date=travel_date,
        booking_status="pending",
        amount_paid=100.0,
        booking_details={},
        route_id=route_id,
    )
    db_session.add(booking)
    db_session.flush()
    payment = Payment(
        id=str(uuid.uuid4()),
        booking_id=booking.id,
        razorpay_order_id=f"order-{uuid.uuid4()}",
        status=status,
        amount=100.0,
    )
    db_session.add(payment)
    db_session.commit()
    return booking, payment


def test_payment_status_endpoint(auth_client, db_session):
    client, user = auth_client
    # create booking/payment with completed status
    _, payment = create_booking_and_payment(db_session, user, status="completed")

    resp = client.get(f"/api/payments/status/{payment.razorpay_order_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_id"] == payment.razorpay_order_id
    assert data["status"] == "completed"


def test_payment_history_pagination(auth_client, db_session):
    client, user = auth_client
    # create two payments
    create_booking_and_payment(db_session, user, route_id="route-1", travel_date="2026-03-01", status="completed")
    create_booking_and_payment(db_session, user, route_id="route-2", travel_date="2026-03-02", status="pending")

    # request with limit=1
    resp = client.get("/api/payments/booking/history?skip=0&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["total"] >= 2
    assert len(data["payments"]) == 1
    assert data["skip"] == 0
    assert data["limit"] == 1


def test_check_payment_status_endpoint(auth_client, db_session):
    client, user = auth_client
    booking, payment = create_booking_and_payment(db_session, user, route_id="route-abc", travel_date="2026-04-01", status="completed")

    resp = client.get("/api/payments/check_payment_status", params={
        "route_id": booking.route_id,
        "travel_date": booking.travel_date,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["paid"] is True
    assert data.get("already_paid_booking") is True


def test_webhook_payment_event_updates_status(auth_client, db_session):
    """Simulate a Razorpay payment.captured webhook and verify DB update."""
    client, user = auth_client
    _, payment = create_booking_and_payment(db_session, user, status="pending")
    # assign razorpay payment id so webhook can match
    payment.razorpay_payment_id = "pay_abc"
    payment.razorpay_order_id = "order_xyz"
    payment.status = "pending"
    db_session.commit()

    payload = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_abc", "order_id": "order_xyz", "status": "captured"}}}
    }
    resp = client.post("/api/payments/webhook", json=payload)
    assert resp.status_code == 200

    db_session.refresh(payment)
    assert payment.status == "completed"

    # send same event again to ensure idempotency
    resp2 = client.post("/api/payments/webhook", json=payload)
    assert resp2.status_code == 200
    assert resp2.json().get("message") == "already processed"


def test_webhook_refund_event_updates_status(auth_client, db_session):
    """Simulate a Razorpay refund event and ensure refund record updates."""
    client, user = auth_client
    # create dummy refund record
    from backend.database.models import Refund
    refund = Refund(
        id="ref-1",
        booking_request_id="req-1",
        amount=100.0,
        currency="INR",
        status="PENDING",
        razorpay_refund_id="refund_123",
    )
    db_session.add(refund)
    db_session.commit()

    payload = {
        "event": "refund.processed",
        "payload": {"refund": {"entity": {"id": "refund_123", "status": "processed"}}}
    }
    resp = client.post("/api/payments/webhook", json=payload)
    assert resp.status_code == 200

    db_session.refresh(refund)
    assert refund.status == "COMPLETED"

    # duplicate refund event should be ignored
    resp2 = client.post("/api/payments/webhook", json=payload)
    assert resp2.status_code == 200
    assert resp2.json().get("message") == "already processed"
