import os
import json
import smtplib
import requests
from unittest.mock import patch
from routemaster_agent.alerting import _compose_summary_text, notify_test_summary


def test_compose_text():
    summary = {"total":2, "passed":1, "failed":1, "results":[{"train_number":"11603","validation_passed":False,"errors":["err"]}], "artifacts_path":"/tmp"}
    txt = _compose_summary_text(summary)
    assert "11603" in txt


def test_notify_persists_and_requests_dashboard_update():
    summary = {"total":1, "passed":0, "failed":1, "results":[{"train_number":"11603","validation_passed":False,"errors":["err"], "selector_failures":0}], "artifacts_path":"/tmp"}
    # Even if envs exist, this service will not send outbound messages; it should persist alerts and
    # mark that a dashboard update is required so the UI/Grafana can surface the alert.
    os.environ['RMA_SLACK_WEBHOOK_URL'] = 'https://example.com'
    os.environ['RMA_ALERT_EMAILS'] = 'ops@example.com'
    res = notify_test_summary(summary)
    assert res.get('db_logged') is True
    assert res.get('dashboard_update') is True
    assert isinstance(res.get('alerts_created'), dict)