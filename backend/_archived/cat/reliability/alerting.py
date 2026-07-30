"""
Alerting utilities for the Contextual Availability Transformer (CAT) system.
Provides alerting for critical events and threshold violations.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import deque, defaultdict
import asyncio

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """An alert for a critical event."""
    id: str
    severity: AlertSeverity
    title: str
    description: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    component: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "component": self.component,
            "metadata": self.metadata,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved
        }


class AlertManager:
    """
    Alert manager for CAT system.
    
    Manages alerts for latency, data freshness, model reload failures, and error rates.
    """
    
    def __init__(
        self,
        latency_slo_ms: float = 200.0,
        data_freshness_threshold_seconds: float = 300.0,
        error_rate_threshold_percent: float = 5.0,
        model_reload_failure_threshold: int = 3
    ):
        """
        Initialize the alert manager.
        
        Args:
            latency_slo_ms: SLO for prediction latency in milliseconds
            data_freshness_threshold_seconds: Threshold for data freshness in seconds
            error_rate_threshold_percent: Threshold for error rate percentage
            model_reload_failure_threshold: Number of failures before alerting
        """
        self._latency_slo_ms = latency_slo_ms
        self._data_freshness_threshold = data_freshness_threshold_seconds
        self._error_rate_threshold = error_rate_threshold_percent
        self._model_reload_failure_threshold = model_reload_failure_threshold
        
        self._alerts: Dict[str, Alert] = {}
        self._alert_history: deque = deque(maxlen=1000)
        self._failure_counts: Dict[str, int] = defaultdict(int)
        self._last_success_times: Dict[str, datetime] = {}
        
        # Alert handlers (can be overridden for custom behavior)
        self._handlers: List[Callable[[Alert], None]] = []
        
        # Add default handler that logs alerts
        self.add_handler(self._default_handler)
    
    def _default_handler(self, alert: Alert) -> None:
        """Default alert handler that logs alerts."""
        if alert.severity == AlertSeverity.CRITICAL:
            logger.critical(f"CRITICAL ALERT: {alert.title} - {alert.description}")
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning(f"WARNING ALERT: {alert.title} - {alert.description}")
        else:
            logger.info(f"INFO ALERT: {alert.title} - {alert.description}")
    
    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """
        Add an alert handler.
        
        Args:
            handler: Callable that takes an Alert
        """
        self._handlers.append(handler)
    
    def _notify_handlers(self, alert: Alert) -> None:
        """Notify all handlers of an alert."""
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
    
    def _create_alert(
        self,
        severity: AlertSeverity,
        title: str,
        description: str,
        component: str = "system",
        metadata: Dict[str, Any] = None
    ) -> Alert:
        """Create a new alert."""
        import uuid
        alert_id = str(uuid.uuid4())[:8]
        
        alert = Alert(
            id=alert_id,
            severity=severity,
            title=title,
            description=description,
            component=component,
            metadata=metadata or {}
        )
        
        self._alerts[alert_id] = alert
        self._alert_history.append(alert)
        self._notify_handlers(alert)
        
        return alert
    
    def _resolve_alert(self, alert_id: str) -> None:
        """Resolve an alert."""
        if alert_id in self._alerts:
            self._alerts[alert_id].resolved = True
            self._alerts[alert_id].acknowledged = True
    
    def check_latency(self, latency_ms: float) -> Optional[Alert]:
        """
        Check if latency exceeds SLO and create alert if needed.
        
        Args:
            latency_ms: Latency in milliseconds
            
        Returns:
            Alert if SLO exceeded, None otherwise
        """
        if latency_ms > self._latency_slo_ms:
            alert = self._create_alert(
                severity=AlertSeverity.WARNING,
                title="Prediction Latency Exceeds SLO",
                description=f"Latency {latency_ms:.1f}ms exceeds SLO of {self._latency_slo_ms}ms",
                component="inference",
                metadata={"latency_ms": latency_ms, "slo_ms": self._latency_slo_ms}
            )
            return alert
        return None
    
    def check_data_freshness(self, freshness_seconds: float) -> Optional[Alert]:
        """
        Check if data freshness exceeds threshold and create alert if needed.
        
        Args:
            freshness_seconds: Data freshness in seconds
            
        Returns:
            Alert if threshold exceeded, None otherwise
        """
        if freshness_seconds > self._data_freshness_threshold:
            alert = self._create_alert(
                severity=AlertSeverity.WARNING,
                title="Data Freshness Exceeds Threshold",
                description=f"Data freshness {freshness_seconds:.1f}s exceeds threshold of {self._data_freshness_threshold}s",
                component="data_collection",
                metadata={"freshness_seconds": freshness_seconds, "threshold_seconds": self._data_freshness_threshold}
            )
            return alert
        return None
    
    def record_model_reload_failure(self) -> Optional[Alert]:
        """
        Record a model reload failure and create alert if threshold reached.
        
        Returns:
            Alert if threshold reached, None otherwise
        """
        self._failure_counts["model_reload"] += 1
        
        if self._failure_counts["model_reload"] >= self._model_reload_failure_threshold:
            alert = self._create_alert(
                severity=AlertSeverity.CRITICAL,
                title="Model Reload Failure Threshold Reached",
                description=f"Model reload failed {self._failure_counts['model_reload']} times",
                component="model",
                metadata={"failure_count": self._failure_counts["model_reload"], "threshold": self._model_reload_failure_threshold}
            )
            return alert
        return None
    
    def record_model_reload_success(self) -> None:
        """Record a successful model reload."""
        self._failure_counts["model_reload"] = 0
        self._last_success_times["model_reload"] = datetime.utcnow()
    
    def check_error_rate(self, error_rate_percent: float) -> Optional[Alert]:
        """
        Check if error rate exceeds threshold and create alert if needed.
        
        Args:
            error_rate_percent: Error rate as percentage
            
        Returns:
            Alert if threshold exceeded, None otherwise
        """
        if error_rate_percent > self._error_rate_threshold:
            alert = self._create_alert(
                severity=AlertSeverity.WARNING,
                title="High Error Rate Detected",
                description=f"Error rate {error_rate_percent:.1f}% exceeds threshold of {self._error_rate_threshold}%",
                component="system",
                metadata={"error_rate_percent": error_rate_percent, "threshold_percent": self._error_rate_threshold}
            )
            return alert
        return None
    
    def record_request_success(self, component: str = "system") -> None:
        """Record a successful request for a component."""
        self._last_success_times[component] = datetime.utcnow()
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active (non-resolved) alerts."""
        return [a for a in self._alerts.values() if not a.resolved]
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history."""
        return list(self._alert_history)[-limit:]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID to acknowledge
            
        Returns:
            True if alert was acknowledged, False if not found
        """
        if alert_id in self._alerts:
            self._alerts[alert_id].acknowledged = True
            return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID to resolve
            
        Returns:
            True if alert was resolved, False if not found
        """
        if alert_id in self._alerts:
            self._alerts[alert_id].resolved = True
            self._alerts[alert_id].acknowledged = True
            return True
        return False
    
    def get_summary(self) -> Dict[str, Any]:
        """Get alert summary."""
        active_alerts = self.get_active_alerts()
        
        return {
            "active_alerts": len(active_alerts),
            "critical_alerts": len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]),
            "warning_alerts": len([a for a in active_alerts if a.severity == AlertSeverity.WARNING]),
            "info_alerts": len([a for a in active_alerts if a.severity == AlertSeverity.INFO]),
            "total_alerts": len(self._alerts),
            "alert_history_size": len(self._alert_history)
        }


def create_alert_manager() -> AlertManager:
    """
    Factory function to create an AlertManager.
    
    Returns:
        Configured AlertManager instance
    """
    return AlertManager()
