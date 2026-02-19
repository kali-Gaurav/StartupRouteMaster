import json
import pytest
from fastapi.testclient import TestClient

from backend.api.admin import router as admin_router
from backend.app import app

client = TestClient(app)


def test_trigger_perf_check_schedules(monkeypatch):
    called = {}

    def fake_run_perf_check(*args, **kwargs):
        called['ok'] = True
        return {"success": True, "result": {"median_runtime_ms": 5.0, "p95_runtime_ms": 10.0}}

    monkeypatch.setattr('backend.services.perf_check.run_perf_check', fake_run_perf_check)

    resp = client.post('/api/admin/perf-check?stations=10&route_length=3&queries=5&ml_enabled=false', headers={
        'x-admin-token': 'invalid-token'
    })
    assert resp.status_code == 401

    # use real token from config (or set a test override)
    from backend.config import Config
    resp = client.post(f'/api/admin/perf-check?stations=10&route_length=3&queries=5&ml_enabled=false&token={Config.ADMIN_API_TOKEN}')
    # admin endpoint expects token via query param in this route; ensure accepted
    assert resp.status_code in (200, 202)


def test_get_perf_check_status(monkeypatch):
    monkeypatch.setattr('backend.services.perf_check.get_last_result', lambda: {"success": True, "result": {"p95_runtime_ms": 10.0}})
    from backend.config import Config
    resp = client.get(f'/api/admin/perf-check/status?token={Config.ADMIN_API_TOKEN}')
    assert resp.status_code == 200
    body = resp.json()
    assert 'last' in body
