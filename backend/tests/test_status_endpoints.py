from fastapi.testclient import TestClient

from app import app


def test_health_components_and_readiness():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        health_data = health.json()
        assert "status" in health_data
        assert "components" in health_data
        for key in ("database", "redis", "route_engine", "external_api", "routers", "middleware"):
            assert key in health_data["components"]

        ready = client.get("/api/health/ready")
        assert ready.status_code == 200
        ready_data = ready.json()
        assert ready_data["status"] in {"ready", "degraded"}
        assert "database" in ready_data
        assert "route_engine" in ready_data
        assert "components" in ready_data
