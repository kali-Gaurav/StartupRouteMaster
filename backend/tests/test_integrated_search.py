from fastapi.testclient import TestClient
import pytest
import uuid
import logging

# silence noisy SQLAlchemy engine logs during these simple endpoint tests
logging.getLogger('sqlalchemy.engine.Engine').setLevel(logging.WARNING)

from backend.app import app
from backend.api.dependencies import get_current_user
from backend.services.search_service import SearchService


@pytest.fixture(scope="function")
def auth_client(db_session, monkeypatch):
    # re-use same auth_client strategy from payment tests
    from backend.database.models import User
    from backend.core.route_engine import route_engine

    # prevent route engine warmup from hitting missing methods by stubbing search
    async def dummy_search(*args, **kwargs):
        return []
    monkeypatch.setattr(route_engine, "search_routes", dummy_search)

    user = User(id=str(uuid.uuid4()), email=f"user+{uuid.uuid4()}@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    def _override_current_user():
        return user

    app.dependency_overrides[get_current_user] = _override_current_user
    with TestClient(app) as client:
        yield client, user
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unlock_details_includes_graph_and_summary(auth_client, monkeypatch):
    client, user = auth_client

    # patch the service method to return a controlled payload
    async def fake_unlock(self, journey_id, travel_date_str, coach_preference="AC_THREE_TIER", passenger_age=30, concession_type=None):
        # mimic return structure of real method with all required fields
        return {
            "journey": {
                "journey_id": journey_id,
                "num_segments": 1,
                "distance_km": 100.0,
                "travel_time": "02:00",
                "num_transfers": 0,
                "is_direct": True,
                "cheapest_fare": 500.0,
                "premium_fare": 1100.0,
                "has_overnight": False,
                "availability_status": "AVAILABLE"
            },
            "seat_allocation": {},
            "verification": {},
            "fare_breakdown": {},
            "can_unlock_details": True,
            "route_graph": {"nodes": [], "edges": [], "is_direct": True},
            "verification_summary": {"rapidapi_calls": 0, "seat_availability": {}, "fare_verification": {}, "warnings": []}
        }

    monkeypatch.setattr(SearchService, "unlock_journey_details", fake_unlock)

    resp = client.get("/api/v2/journey/test_journey/unlock-details", params={"travel_date": "2026-03-01"})
    # debug information for failures
    print("HTTP status", resp.status_code)
    try:
        print("response body", resp.json())
    except Exception:
        print("response text", resp.text)
    assert resp.status_code == 200
    data = resp.json()
    assert "route_graph" in data
    assert data["route_graph"]["is_direct"] is True
    assert "verification_summary" in data
    assert data["verification_summary"]["rapidapi_calls"] == 0
+
+
+@pytest.mark.asyncio
+async def test_search_routes_verification_integration(auth_client, monkeypatch):
+    client, user = auth_client
+
+    # monkeypatch route_engine.search_routes to return two dummy routes
+    async def fake_search(*args, **kwargs):
+        # create objects with minimal attributes used by SearchService
+        class DummySeg:
+            def __init__(self, trip_id, dep_id, arr_id, dep_time, arr_time, train_no):
+                self.trip_id = trip_id
+                self.departure_stop_id = dep_id
+                self.arrival_stop_id = arr_id
+                self.departure_time = dep_time
+                self.arrival_time = arr_time
+                self.train_number = train_no
+
+        class DummyRoute:
+            def __init__(self, segments):
+                self.segments = segments
+                self.transfers = []
+                self.total_duration = 120
+                self.total_distance = 100
+                self.total_cost = 500
+
+        from datetime import datetime
+        r1 = DummyRoute([DummySeg(1, 10, 20, datetime.now(), datetime.now(), "12345")])
+        r2 = DummyRoute([DummySeg(2, 30, 40, datetime.now(), datetime.now(), "67890")])
+        return [r1, r2]
+
+    monkeypatch.setattr('backend.core.route_engine.route_engine', 'search_routes', fake_search)
+
+    # patch the verification engine to return predetermined summaries
+    async def fake_verify_batch(self, candidates, travel_date, coach_preference, quota="GN"):
+        return [{
+            "journey_id": c["journey_id"],
+            "status": "verified",
+            "verified": True,
+            "verification_calls": {"live": True, "seat": True, "fare": True},
+            "live_status": {"success": True},
+            "seat_availability": {"success": True},
+            "fare": {"success": True},
+            "cached": False
+        } for c in candidates]
+
+    monkeypatch.setattr(RouteVerificationEngine, "verify_routes_batch", fake_verify_batch)
+
+    resp = client.get("/api/v2/search", params={"source":"NDLS","destination":"MMCT","travel_date":"2026-03-01"})
+    assert resp.status_code == 200
+    data = resp.json()
+    assert "journeys" in data
+    for journey in data["journeys"]:
+        assert journey.get("verification_summary", {}).get("status") == "verified"
*** End Patch
