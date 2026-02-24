from backend.app import app
from backend.database import SessionLocal
from backend.database.models import User, Booking, Payment
from backend.api.dependencies import get_current_user, verify_webhook_signature
from fastapi.testclient import TestClient
import uuid
from datetime import datetime


db = SessionLocal()
user = User(id=str(uuid.uuid4()), email=f"user+{uuid.uuid4()}@example.com", password_hash="hash")
db.add(user)
db.commit()
BookingObj = Booking(
    id=str(uuid.uuid4()),
    pnr_number=str(uuid.uuid4())[:10],
    user_id=user.id,
    travel_date=datetime.fromisoformat("2026-03-01").date(),
    booking_status="pending",
    amount_paid=100.0,
    booking_details={},
    route_id="route-123",
)
db.add(BookingObj)
db.flush()
payment = Payment(
    id=str(uuid.uuid4()),
    booking_id=BookingObj.id,
    razorpay_order_id="order-bug",
    status="pending",
    amount=100.0,
)
db.add(payment)
db.commit()
payment.razorpay_payment_id = "pay_abc"
payment.razorpay_order_id = "order_xyz"
payment.status = "pending"
db.commit()

with TestClient(app) as client:
    client.dependency_overrides[get_current_user] = lambda: user
    client.dependency_overrides[verify_webhook_signature] = lambda request: None
    payload = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_abc", "order_id": "order_xyz", "status": "captured"}}}
    }
    resp = client.post("/api/payments/webhook", json=payload)
    print("status", resp.status_code)
    print(resp.text)
    print(resp.headers)
