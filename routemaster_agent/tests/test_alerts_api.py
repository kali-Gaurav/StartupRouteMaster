import os
import asyncio
from fastapi.testclient import TestClient
from routemaster_agent.main import app
from routemaster_agent.alerting import notify_test_summary
from routemaster_agent.database.db import SessionLocal
from routemaster_agent.database.models import Alert

client = TestClient(app)


def test_alerts_api_and_resolve(monkeypatch):
    # ensure clean DB
    session = SessionLocal()
    session.query(Alert).delete()
    session.commit()
    session.close()

    # create a failing summary and call notifier
    summary = {"total":1, "passed":0, "failed":1, "results":[{"train_number":"55555","validation_passed":False,"errors":["err"]}], "artifacts_path":"/tmp"}
    notify_test_summary(summary)

    # fetch alerts via API
    resp = client.get('/api/admin/rma-alerts')
    assert resp.status_code == 200
    data = resp.json()
    assert 'alerts' in data
    assert any(a['train_number']=='55555' for a in data['alerts'])

    # resolve an alert
    alert_id = data['alerts'][0]['id']
    resp2 = client.post(f'/api/admin/rma-alerts/{alert_id}/resolve')
    assert resp2.status_code == 200
    assert resp2.json().get('ok') is True

    # verify resolved flag
    session = SessionLocal()
    a = session.query(Alert).filter(Alert.id == alert_id).first()
    assert a.resolved is True
    session.close()