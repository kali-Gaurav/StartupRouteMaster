"""
Bridge module: re-exports the canonical alert_service singleton from alerts.py.
system_monitor.py (and any other consumer) can import from either path.
"""
from services.communication.alerts import AlertService, AlertLevel, AlertStatus, Alert, alert_service  # noqa: F401

__all__ = ["AlertService", "AlertLevel", "AlertStatus", "Alert", "alert_service"]
