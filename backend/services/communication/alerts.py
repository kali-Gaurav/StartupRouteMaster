"""
Alert Service - Observability and Alerting System
==================================================

Provides hooks for Slack/Discord/Email notifications for critical events:
- Structured alert sending
- SLA monitoring
- Rate limiting to prevent alert floods
- Multi-platform webhook support

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import logging
import httpx
import os
import time
import platform
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from core.resilience.core import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy, retry

logger = logging.getLogger("routemaster.alerts")


class AlertLevel(Enum):
    """Alert severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertStatus(Enum):
    """Status of alert sending."""
    SENT = "SENT"
    RATE_LIMITED = "RATE_LIMITED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class Alert:
    """Alert structure."""
    title: str
    message: str
    level: AlertLevel
    timestamp: datetime
    extra: Dict[str, Any] = field(default_factory=dict)
    status: AlertStatus = AlertStatus.SENT
    attempts: int = 0


class AlertService:
    """
    🛡️ TASK 13: Observability System - Alerting & SLA Monitoring
    Provides hooks for Slack/Discord/Email notifications for critical events.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize alert service with resilience patterns."""
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        self.env = os.getenv("ENVIRONMENT", "production")
        self._last_alert_time: Dict[str, float] = {}
        self._cooldown = 300  # 5 minutes per unique alert type
        
        # Circuit breaker for HTTP operations
        self._http_breaker = circuit_breaker_manager.get_or_create(
            "alert_service_http",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=10.0,
                success_threshold=3
            )
        )
        
        # Retry policy for HTTP operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: isinstance(e, httpx.TimeoutException),
                lambda e: isinstance(e, httpx.ConnectError),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Alert history
        self._alert_history: deque = deque(maxlen=100)
        self._history_lock = asyncio.Lock()
        
        # SLA tracking
        self._sla_violations: deque = deque(maxlen=100)
        self._sla_lock = asyncio.Lock()
        
        logger.info("AlertService initialized with resilience patterns")

    def _get_cache_key(self, level: str, title: str) -> str:
        """Generate cache key for rate limiting."""
        return f"{level}:{title}"

    def _should_rate_limit(self, cache_key: str) -> bool:
        """Check if alert should be rate limited."""
        from time import time
        if cache_key in self._last_alert_time:
            if time() - self._last_alert_time[cache_key] < self._cooldown:
                return True
        return False

    def _format_slack_payload(self, title: str, message: str, level: str, extra: Dict[str, Any]) -> Dict[str, Any]:
        """Format payload for Slack/Discord."""
        color_map = {
            "CRITICAL": "#FF0000",  # Red
            "ERROR": "#FF8C00",     # Dark orange
            "WARNING": "#FFD700",   # Gold
            "INFO": "#00FF00",      # Green
            "DEBUG": "#808080"      # Gray
        }
        
        return {
            "username": "RouteMaster Sentry",
            "attachments": [{
                "color": color_map.get(level, "#808080"),
                "title": f"[{self.env.upper()}] {level}: {title}",
                "text": f"{message}\n\n*Server*: {platform.node()}\n*Env*: {self.env}",
                "footer": "RouteMaster V3 Observability Engine",
                "fields": [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in extra.items()
                ] if extra else []
            }]
        }

    @retry(
        max_attempts=3,
        initial_delay=0.5,
        max_delay=5.0,
        conditions=[
            lambda e: isinstance(e, httpx.TimeoutException),
            lambda e: isinstance(e, httpx.ConnectError)
        ]
    )
    async def _send_webhook(self, url: str, payload: Dict[str, Any]) -> bool:
        """Send alert to webhook."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return True

    async def send_alert(
        self,
        title: str,
        message: str,
        level: str = "ERROR",
        extra: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """
        Sends a structured alert to the configured webhook.
        
        Args:
            title: Alert title
            message: Alert message
            level: Alert level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            extra: Additional fields for the alert
            
        Returns:
            Alert with status information
            
        Protected by circuit breaker and retry logic.
        """
        alert = Alert(
            title=title,
            message=message,
            level=AlertLevel(level),
            timestamp=datetime.utcnow(),
            extra=extra or {}
        )
        
        if not self.webhook_url:
            alert.status = AlertStatus.SKIPPED
            logger.warning(
                f"⚠️ Alert discarded (No Webhook): [{level}] {title} - {message}"
            )
            await self._record_alert(alert)
            return alert

        webhook_url = self.webhook_url
        assert webhook_url is not None

        # Simple rate-limiting to prevent alert floods
        cache_key = self._get_cache_key(level, title)
        if self._should_rate_limit(cache_key):
            alert.status = AlertStatus.RATE_LIMITED
            logger.debug(f"⏳ Alert rate limited: {title}")
            await self._record_alert(alert)
            return alert

        self._last_alert_time[cache_key] = time.time()

        # Format payload
        payload = self._format_slack_payload(title, message, level, extra or {})

        async def _send_with_breaker():
            """Send through circuit breaker."""
            return await self._send_webhook(webhook_url, payload)

        try:
            await self._http_breaker.execute(
                self._retry_policy.execute,
                _send_with_breaker
            )
            alert.status = AlertStatus.SENT
            logger.info(f"🚀 Alert sent: {title}")
            
        except Exception as e:
            alert.status = AlertStatus.FAILED
            logger.error(f"❌ Failed to send alert: {e}")

        await self._record_alert(alert)
        return alert

    async def monitor_sla(
        self,
        duration_ms: float,
        path: str,
        threshold_ms: float = 2000.0
    ) -> Optional[Alert]:
        """
        Tracks SLA compliance (99% within threshold_ms).
        
        Args:
            duration_ms: Request duration in milliseconds
            path: Request path
            threshold_ms: SLA threshold (default 2000ms)
            
        Returns:
            Alert if SLA violated, None otherwise
        """
        if duration_ms > threshold_ms:
            alert = await self.send_alert(
                "SLA Violation",
                f"Request to {path} took {duration_ms:.0f}ms (threshold: {threshold_ms}ms)",
                level="WARNING",
                extra={"path": path, "duration": duration_ms, "threshold": threshold_ms}
            )
            
            # Track SLA violation
            await self._record_sla_violation(path, duration_ms, threshold_ms)
            return alert
        
        return None

    async def send_batch_alerts(self, alerts: List[Dict[str, Any]]) -> List[Alert]:
        """
        Send multiple alerts efficiently.
        
        Args:
            alerts: List of alert dicts with title, message, level, extra
            
        Returns:
            List of Alert results
        """
        results = []
        for alert_data in alerts:
            result = await self.send_alert(
                title=alert_data.get("title", "Alert"),
                message=alert_data.get("message", ""),
                level=alert_data.get("level", "INFO"),
                extra=alert_data.get("extra")
            )
            results.append(result)
        
        return results

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_alert(self, alert: Alert):
        """Record alert for metrics and history."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": alert.timestamp,
                "title": alert.title,
                "level": alert.level.value,
                "status": alert.status.value,
                "attempts": alert.attempts
            })
        
        async with self._history_lock:
            self._alert_history.append({
                "title": alert.title,
                "level": alert.level.value,
                "status": alert.status.value,
                "timestamp": alert.timestamp.isoformat()
            })

    async def _record_sla_violation(
        self,
        path: str,
        duration_ms: float,
        threshold_ms: float
    ):
        """Record SLA violation for tracking."""
        async with self._sla_lock:
            self._sla_violations.append({
                "timestamp": datetime.utcnow(),
                "path": path,
                "duration_ms": duration_ms,
                "threshold_ms": threshold_ms,
                "violation_ratio": duration_ms / threshold_ms
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_alerts": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        sent = sum(1 for m in self._metrics if m["status"] == "SENT")
        rate_limited = sum(1 for m in self._metrics if m["status"] == "RATE_LIMITED")
        failed = sum(1 for m in self._metrics if m["status"] == "FAILED")
        
        by_level = {}
        for m in self._metrics:
            level = m.get("level", "UNKNOWN")
            by_level[level] = by_level.get(level, 0) + 1
        
        return {
            "total_alerts": total,
            "sent_alerts": sent,
            "rate_limited_alerts": rate_limited,
            "failed_alerts": failed,
            "success_rate": sent / total if total > 0 else 0.0,
            "by_level": by_level,
            "circuit_breaker_state": self._http_breaker.get_state().value
        }

    def get_sla_metrics(self) -> dict:
        """Get SLA monitoring metrics."""
        if not self._sla_violations:
            return {"total_violations": 0, "avg_violation_ratio": 0.0}
        
        total = len(self._sla_violations)
        ratios = [v["violation_ratio"] for v in self._sla_violations]
        
        # Group by path
        by_path = {}
        for v in self._sla_violations:
            path = v["path"]
            if path not in by_path:
                by_path[path] = []
            by_path[path].append(v["violation_ratio"])
        
        return {
            "total_violations": total,
            "avg_violation_ratio": sum(ratios) / len(ratios) if ratios else 0,
            "max_violation_ratio": max(ratios) if ratios else 0,
            "by_path": {
                path: {
                    "count": len(ratios),
                    "avg_ratio": sum(ratios) / len(ratios)
                }
                for path, ratios in by_path.items()
            }
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "webhook_configured": self.webhook_url is not None,
            "circuit_breaker": {
                "state": self._http_breaker.get_state().value,
                "failure_count": self._http_breaker.failure_count,
                "success_count": self._http_breaker.success_count
            },
            "metrics": self.get_metrics(),
            "sla_metrics": self.get_sla_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._http_breaker.reset()
        logger.info("Circuit breaker reset for alert service")

    def get_alert_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent alert history."""
        return list(self._alert_history)[-limit:]

    def clear_rate_limit(self, level: Optional[str] = None, title: Optional[str] = None):
        """Clear rate limit for specific alert or all alerts."""
        if level and title:
            key = self._get_cache_key(level, title)
            self._last_alert_time.pop(key, None)
        else:
            self._last_alert_time.clear()
        logger.info(f"Rate limits cleared for {'all' if not (level and title) else f'{level}:{title}'}")


# Global instance
alert_service = AlertService()
