from fastapi.testclient import TestClient
from backend.app import app
from backend.services.route_engine import route_engine

print('before TestClient, is_loaded =', route_engine.is_loaded())
with TestClient(app) as client:
    print('inside TestClient context, is_loaded =', route_engine.is_loaded())
    resp = client.get('/api/health/ready')
    print('GET /api/health/ready ->', resp.status_code, resp.text)

print('after TestClient context, is_loaded =', route_engine.is_loaded())
