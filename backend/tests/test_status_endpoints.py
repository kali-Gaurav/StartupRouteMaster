from fastapi.testclient import TestClient
from backend.app import app
import pytest


def test_health_components_and_readiness(monkeypatch):
    # create client which will trigger startup events
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "components" in data
        comps = data["components"]
        # expect keys
        for key in ("database", "redis", "route_engine", "external_api"):
            assert key in comps
        # readiness should return ready once startup is finished
        r2 = client.get("/api/health/ready")
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["status"] == "ready"
        assert data2["components"]["database"] == "ready"
        assert data2["components"]["route_engine"] == "loaded"


@pytest.mark.asyncio
async def test_external_api_health_before_and_after():
    # manually manipulate external_api_health to simulate freshness
    from backend.utils.external_api_health import record_success, is_fresh
    record_success()  # now should be fresh
    assert is_fresh() is True

    # backdate beyond threshold
    import datetime
    from backend.utils import external_api_health
    external_api_health._last_success = datetime.datetime.utcnow() - external_api_health.STALE_THRESHOLD * 2
    assert is_fresh() is False
