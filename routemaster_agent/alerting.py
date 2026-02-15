import os
import json
import smtplib
from email.message import EmailMessage
from typing import Dict, Any, List
import requests

SLACK_WEBHOOK = os.getenv("RMA_SLACK_WEBHOOK_URL") or os.getenv("RMA_SLACK_WEBHOOK")
ALERT_EMAILS = os.getenv("RMA_ALERT_EMAILS")  # comma-separated
SMTP_HOST = os.getenv("RMA_SMTP_HOST")
SMTP_PORT = int(os.getenv("RMA_SMTP_PORT" or 0) or 0)
SMTP_USER = os.getenv("RMA_SMTP_USER")
SMTP_PASS = os.getenv("RMA_SMTP_PASS")
SMTP_FROM = os.getenv("RMA_SMTP_FROM", "noreply@routemaster.local")
SELECTOR_FAILURE_THRESHOLD = int(os.getenv("RMA_SELECTOR_FAILURE_THRESHOLD", "5"))


def _send_slack_message(text: str) -> bool:
    webhook = SLACK_WEBHOOK
    if not webhook:
        return False
    try:
        resp = requests.post(webhook, json={"text": text}, timeout=10)
        return resp.status_code >= 200 and resp.status_code < 300
    except Exception:
        return False


def _send_email(subject: str, body: str, recipients: List[str]) -> bool:
    if not SMTP_HOST or not recipients:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = ", ".join(recipients)
        msg.set_content(body)

        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.starttls()
        if SMTP_USER and SMTP_PASS:
            server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception:
        return False


def _compose_summary_text(summary: Dict[str, Any]) -> str:
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    lines = [f"RouteMaster Agent QA — {total} trains tested: {passed} passed, {failed} failed"]
    for r in summary.get("results", []):
        if not r.get("validation_passed"):
            lines.append(f"- FAILED: {r.get('train_number')} (errors: {r.get('errors')})")
    lines.append(f"Artifacts: {summary.get('artifacts_path')}")
    return "\n".join(lines)


def notify_test_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Record alerts (persist to DB) and optionally send Slack notifications.
    Email notifications are disabled by default — alerts are shown on the dashboard.
    Returns a dict summarizing notification + storage actions.
    """
    results = {"slack": None, "db_logged": None, "reason": None}
    try:
        failed = summary.get("failed", 0)
        selector_spikes = any((r.get("selector_failures", 0) or 0) >= int(os.getenv('RMA_SELECTOR_FAILURE_THRESHOLD', str(SELECTOR_FAILURE_THRESHOLD))) for r in summary.get("results", []))

        if failed == 0 and not selector_spikes:
            results["reason"] = "no-failures"
            return results

        text = _compose_summary_text(summary)

        # Persist alerts into DB so dashboard can display them
        try:
            from routemaster_agent.database.db import SessionLocal
            from routemaster_agent.database.models import Alert
            session = SessionLocal()
            # top-level summary alert
            summary_alert = Alert(source='rma_test_summary', train_number=None, level='critical' if failed>0 else 'warning', message=text, meta=summary)
            session.add(summary_alert)
            # per-train alerts
            for r in summary.get('results', []):
                if not r.get('validation_passed') or (r.get('selector_failures') or 0) >= int(os.getenv('RMA_SELECTOR_FAILURE_THRESHOLD', str(SELECTOR_FAILURE_THRESHOLD))):
                    a = Alert(source='rma_test', train_number=r.get('train_number'), level='critical', message=f"Test failed for {r.get('train_number')}", meta=r)
                    session.add(a)
            session.commit()
            results['db_logged'] = True
        except Exception as e:
            results['db_logged'] = False
            results['reason_db'] = str(e)
        finally:
            try:
                session.close()
            except Exception:
                pass

        # Slack (optional)
        webhook = os.getenv('RMA_SLACK_WEBHOOK_URL') or os.getenv('RMA_SLACK_WEBHOOK') or SLACK_WEBHOOK
        if webhook:
            results['slack'] = _send_slack_message(text)

        return results
    except Exception as e:
        results['reason'] = str(e)
        return results