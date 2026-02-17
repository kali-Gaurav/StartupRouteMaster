from fastapi.testclient import TestClient
from datetime import datetime
import json

from app import app

client = TestClient(app)


def test_system_state_endpoint_returns_status():
    resp = client.get("/api/v1/admin/routemaster/system-state")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_trains" in data
    assert "ml_models_loaded" in data
    assert data["status"] in ("healthy", "degraded", "unhealthy")


def test_bulk_insert_trips_smoke():
    payload = {
        "source_system": "test_scraper",
        "trips": [
            {
                "train_number": "99999",
                "train_name": "Test Express",
                "source_code": "NDLS",
                "destination_code": "BCT",
                "stops": [],
                "total_seats": 120,
                "route_type": "TRAIN",
                "service_dates": ["2026-02-20"]
            }
        ]
    }

    resp = client.post("/api/v1/admin/routemaster/bulk-insert-trips", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["inserted_count"] == 1
    assert isinstance(data.get("cache_invalidated"), bool)


def test_update_train_state_not_found():
    payload = {
        "train_number": "NO_SUCH_TRAIN",
        "delay_minutes": 30,
        "status": "delayed",
    }
    resp = client.post("/api/v1/admin/routemaster/update-train-state", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "not found" in data["message"].lower()


def test_pricing_update_route_not_found():
    payload = {
        "source_code": "FAKE",
        "destination_code": "NOSUCH",
        "date": "2026-02-20",
        "current_occupancy": 0.5,
        "predicted_demand": 0.6,
        "recommended_multiplier": 1.25,
        "reasoning": "unit-test"
    }
    resp = client.post("/api/v1/admin/routemaster/pricing-update", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False


def test_rl_feedback_logging_creates_record(db):
    payload = {
        "user_id": "user_test",
        "action": "route_selected",
        "context": {"route_id": 1},
        "reward": 0.8
    }
    resp = client.post("/api/v1/admin/routemaster/rl-feedback", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "feedback_id" in data
