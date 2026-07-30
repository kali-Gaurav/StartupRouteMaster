import pytest
from fastapi.testclient import TestClient

from app import app
from api import websockets


def test_sos_broadcast(monkeypatch):
    """Trigger an SOS and ensure the WebSocket manager broadcast is invoked."""
    recorded = []

    async def fake_broadcast_sos(data):
        recorded.append(data)

    # monkeypatch the async method in manager
    monkeypatch.setattr(websockets.manager, "broadcast_sos", fake_broadcast_sos)

    client = TestClient(app)
    payload = {"lat": 12.34, "lng": 56.78, "name": "Tester"}
    response = client.post("/api/sos", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("lat") == payload["lat"]
    assert len(recorded) == 1
    assert recorded[0]["name"] == "Tester"
