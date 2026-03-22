import logging
import httpx
import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger("routemaster.alerts")

class AlertService:
    """
    🛡️ TASK 13: Observability System - Alerting & SLA Monitoring
    Provides hooks for Slack/Discord/Email notifications for critical events.
    """
    
    def __init__(self):
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        self.env = os.getenv("ENVIRONMENT", "production")
        self._last_alert_time: Dict[str, float] = {}
        self._cooldown = 300 # 5 minutes per unique alert type

    async def send_alert(self, title: str, message: str, level: str = "ERROR", extra: Optional[Dict[str, Any]] = None):
        """Sends a structured alert to the configured webhook."""
        if not self.webhook_url:
            logger.warning(f"⚠️ Alert discarded (No Webhook): [{level}] {title} - {message}")
            return

        # Simple rate-limiting to prevent alert floods
        cache_key = f"{level}:{title}"
        from time import time
        if cache_key in self._last_alert_time:
            if time() - self._last_alert_time[cache_key] < self._cooldown:
                return

        self._last_alert_time[cache_key] = time()

        payload = {
            "title": f"[{self.env.upper()}] {level}: {title}",
            "text": message,
            "timestamp": datetime.utcnow().isoformat(),
            "extra": extra or {}
        }
        
        # Format for Slack/Discord
        slack_payload = {
            "username": "RouteMaster Sentry",
            "attachments": [{
                "color": "danger" if level == "CRITICAL" else "warning" if level == "ERROR" else "good",
                "title": title,
                "text": f"{message}\n\n*Server*: {os.uname().nodename if hasattr(os, 'uname') else 'Windows'}\n*Env*: {self.env}",
                "footer": "RouteMaster V3 Observability Engine"
            }]
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(self.webhook_url, json=slack_payload)
            logger.info(f"🚀 Alert sent: {title}")
        except Exception as e:
            logger.error(f"❌ Failed to send alert: {e}")

    async def monitor_sla(self, duration_ms: float, path: str):
        """Tracks SLA compliance (99% within 2000ms)."""
        if duration_ms > 2000:
            await self.send_alert(
                "SLA Violation", 
                f"Request to {path} took {duration_ms:.0f}ms", 
                level="WARNING",
                extra={"path": path, "duration": duration_ms}
            )

alert_service = AlertService()
