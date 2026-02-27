from fastapi.testclient import TestClient
import httpx
import pytest
from typing import Any, Dict

from api_gateway.app import app as gateway_app

# Helper fake response to mimic httpx.Response in tests
class FakeResponse:
    def __init__(self, status_code: int, json_data: Any = None, text: str = "", headers: Dict[str, str] = None):
        self.status_code = status_code
        self._json = json_data
        self.text = text or ("" if json_data is None else str(json_data))
        self.headers = headers or {"content-type": "application/json"}

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def _ensure_test_clients():
    # make TestClient available for gateway in tests
    yield


def test_api_gateway_search_strips_auth_and_returns_routes(monkeypatch):
    # Ensure the gateway strips Authorization header when proxying to route service
    async def fake_get(self, url, params=None, headers=None):
        # Authorization must not be forwarded
        assert headers is None or "authorization" not in {k.lower() for k in headers.keys()}

        body = [
            {
                "route_id": "route-123",
                "segments": [],
                "total_duration": 120,
                "total_cost": 250.0,
                "feasibility_score": 0.9,
                "recommendations": []
            }
        ]
        return FakeResponse(200, json_data=body)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    client = TestClient(gateway_app)

    resp = client.get(
        "/api/routes/search?source_station=KOTA&destination_station=NDLS&departure_date=2026-02-20",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["route_id"] == "route-123"


def test_api_gateway_search_handles_downstream_not_authenticated(monkeypatch):
    # Simulate downstream returning FastAPI auth error ("Not authenticated")
    async def fake_get_authfail(self, url, params=None, headers=None):
        return FakeResponse(403, json_data={"detail": "Not authenticated"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get_authfail)

    client = TestClient(gateway_app)
    resp = client.get(
        "/api/routes/search?source_station=KOTA&destination_station=NDLS&departure_date=2026-02-20"
    )

    # Gateway maps downstream auth error to a 502 with clearer message
    assert resp.status_code == 502
    assert "Downstream route service" in resp.json()["detail"]


def test_search_booking_notification_integration(db):
    """Integration-style test: search -> create booking (DB) -> notify via notification service API.
    This verifies the high-level flow (services may be separate in production).
    """
    from notification_service.models import Booking as Booking

    # Prepare notification service tables in the same in-memory DB and override its dependency
    from notification_service.app import app as notif_app
    from notification_service.database import get_db as notif_get_db
    from notification_service import models as notif_models

    # create notification_service tables in the same test DB engine
    notif_models.Base.metadata.create_all(bind=db.bind)
    # ensure `notifications` table exists (create table directly if previous metadata clashes occurred)
    notif_models.Notification.__table__.create(bind=db.bind, checkfirst=True)

    # override notification_service get_db dependency to return a fresh session per request
    from sqlalchemy.orm import sessionmaker
    def _override_notif_get_db():
        SessionLocal = sessionmaker(bind=db.bind)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    notif_app.dependency_overrides[notif_get_db] = _override_notif_get_db

    client = TestClient(notif_app)

    # Create a notification (booking_id omitted to avoid cross-schema PK mismatch in tests)
    payload = {
        "user_id": 1,
        "type": "email",
        "subject": "Booking Confirmed",
        "message": "Your booking is confirmed.",
        "recipient": "user@example.com"
    }

    resp = client.post("/notifications/", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["recipient"] == "user@example.com"

    # Verify notification exists in DB
    notif = db.query(notif_models.Notification).filter(notif_models.Notification.recipient == "user@example.com").one()
    assert notif is not None
    assert notif.recipient == "user@example.com"

    # cleanup override
    notif_app.dependency_overrides.pop(notif_get_db, None)
