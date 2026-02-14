import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_api_health_reports_healthy():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "healthy"
    assert data.get("database") == "up"


def test_api_readiness_reports_ready():
    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ready"
    assert data.get("database") == "ready"
    assert data.get("route_engine") == "loaded"


def test_chat_allows_anonymous_requests():
    # Ensure unauthenticated chat POST returns a response (matches CI smoke-tests behavior)
    resp = client.post("/chat", json={"message": "Hello, any trains from Delhi to Mumbai?", "session_id": "anon-smoke"})
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data and "session_id" in data
