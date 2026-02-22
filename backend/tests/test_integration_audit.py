import pytest
import time
import subprocess
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import app
from backend.database import get_db
from backend.database.models import Booking as BookingModel
from backend.schemas import AvailabilityCheckRequestSchema

client = TestClient(app)

# helper to create a short-lived token via auth endpoints
# for the purpose of tests we assume the backend issues both access and refresh tokens

def login_passenger(phone="+911234567890"):
    # hit send-otp and verify-otp endpoints (assumes OTP always '1234' in dev)
    client.post("/api/auth/send-otp", json={"phone": phone})
    resp = client.post(
        "/api/auth/verify-otp",
        json={"phone": phone, "otp": "1234"},
    )
    assert resp.status_code == 200
    return resp.json()["token"], resp.json().get("refresh_token")


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_full_user_flow_and_ws(tmp_path, monkeypatch):
    # Drill 1: passenger searches, checks availability, books, triggers SOS
    token, refresh = login_passenger()

    # search route (simple parameters)
    search_resp = client.post(
        "/api/search/",
        json={"source": "PGT", "destination": "KOTA", "date": "2026-03-01"},
        headers=auth_headers(token),
    )
    assert search_resp.status_code == 200
    routes = search_resp.json().get("routes", {}).get("direct", [])
    assert routes, "expected at least one route"

    # availability check
    avail_payload = {
        "trip_id": routes[0].get("TripId") or routes[0].get("trip_id") or 1,
        "from_stop_id": 1,
        "to_stop_id": 4,
        "travel_date": "2026-03-01",
        "quota_type": "GENERAL",
        "passengers": 1,
    }
    avail_resp = client.post(
        "/api/v1/booking/availability", json=avail_payload, headers=auth_headers(token)
    )
    assert avail_resp.status_code == 200
    avail_data = avail_resp.json()
    assert avail_data.get("available") in (True, False)
    assert "availability_status" in avail_data

    # create a booking via the orchestrator directly (simpler than going through payment)
    booking_payload = {
        "route_id": routes[0].get("RouteId") or routes[0].get("route_id") or str(avail_payload["trip_id"]),
        "travel_date": "2026-03-01",
        "booking_details": {},
        "amount_paid": 0,
        "passenger_details": [{"full_name": "Test User", "age": 30, "gender": "M"}],
    }
    book_resp = client.post(
        "/api/v1/booking/", json=booking_payload, headers=auth_headers(token)
    )
    assert book_resp.status_code == 200
    booking = book_resp.json()
    assert booking.get("passenger_details")

    # verify DB persistence
    # use a separate session to simulate reading after commit
    engine = create_engine(app.dependency_overrides[get_db]().__self__.bind.url)
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    db_booking = sess.query(BookingModel).filter(BookingModel.pnr_number == booking["pnr_number"]).first()
    assert db_booking is not None
    assert len(db_booking.passenger_details) == 1
    sess.close()

    # trigger SOS and listen on responder websocket
    token2, _ = login_passenger("+919876543210")
    # start WS for responder
    import threading
    import websocket as wslib

    alerts = []
    def run_responder():
        url = f"ws://localhost:8000/api/ws/sos?token={token2}"
        ws = wslib.create_connection(url)
        # receive one message and close
        msg = ws.recv()
        alerts.append(msg)
        ws.close()

    thread = threading.Thread(target=run_responder)
    thread.start()
    # send SOS from passenger
    sos_resp = client.post(
        "/api/sos/", json={"lat": 12.34, "lng": 56.78, "name": "Tester"}, headers=auth_headers(token)
    )
    assert sos_resp.status_code == 200
    time.sleep(1)
    thread.join(timeout=5)
    assert alerts, "Responder did not receive SOS"

    # force token expiry by calling refresh endpoint after deleting access token
    newtok_resp = client.post(
        "/api/auth/refresh", json={"refresh_token": refresh}, headers={"Content-Type":"application/json"}
    )
    assert newtok_resp.status_code == 200
    new_token = newtok_resp.json()["access_token"]
    assert new_token != token

    # try availability again using new token
    r2 = client.post(
        "/api/v1/booking/availability", json=avail_payload, headers=auth_headers(new_token)
    )
    assert r2.status_code == 200

    # WebSocket reconnect is automatically handled by hook; here we just ensure a second connection can be made
    ws = wslib.create_connection(f"ws://localhost:8000/api/ws/sos?token={new_token}")
    ws.close()


def test_redis_and_backend_restart_did_not_break(monkeypatch):
    # Drill 2 & 3 are difficult to automate within pytest; instruct user separately
    pytest.skip("Manual verification required: restart Redis/backend during active session.")
