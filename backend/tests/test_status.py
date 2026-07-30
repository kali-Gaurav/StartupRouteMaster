from fastapi.testclient import TestClient

from app import app


def test_api_health_reports_truthful_bootstrap_state():
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in {"healthy", "degraded"}
        assert data["database"] in {"up", "ready", "degraded", "unknown"}
        assert "components" in data
        assert data["components"]["routers"] in {"loaded", "degraded", "disabled"}


def test_api_readiness_reflects_component_state():
    with TestClient(app) as client:
        resp = client.get("/api/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in {"ready", "degraded"}
        assert data["database"] in {"ready", "degraded", "unknown"}
        assert data["route_engine"] in {"loaded", "degraded", "unknown"}
        assert "components" in data
