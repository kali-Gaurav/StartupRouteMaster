"""
BaseAgent — Core Agent Framework
=================================
Every agent inherits from this. Provides lifecycle hooks, event logging,
health monitoring, and execution tracing for the Agent Swarm.
"""
import logging
import asyncio
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DEGRADED = "degraded"
    PAUSED = "paused"


class AgentPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


@dataclass
class AgentEvent:
    """Immutable log entry for an agent action."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_name: str = ""
    action: str = ""
    status: str = "info"
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class AgentMetrics:
    """Running telemetry for each agent."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_duration_ms: float = 0.0
    last_execution: Optional[str] = None
    last_execution_summary: Optional[str] = None
    last_error: Optional[str] = None
    uptime_seconds: float = 0.0
    tasks_queued: int = 0


class BaseAgent:
    """
    Abstract base class for all RouteMaster agents.
    
    Provides:
    - Lifecycle management (init, run, shutdown)
    - Event logging with structured output
    - Health check interface
    - Metrics collection
    - Self-healing retry logic
    """

    name: str = "UnnamedAgent"
    description: str = "No description"
    category: str = "general"
    priority: AgentPriority = AgentPriority.NORMAL
    icon: str = "🤖"
    color: str = "#3B82F6"  # Blue default
    version: str = "1.0.0"
    
    # Config
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    execution_timeout: float = 30.0
    auto_schedule_interval: Optional[float] = None  # seconds between auto-runs

    def __init__(self):
        self.is_active = False
        self.is_paused = False # [G4.3.1] Load-Shedding Flag
        self.last_run = None
        self.logger = logging.getLogger(f"agent.{self.name}")
        self.status = AgentStatus.IDLE
        self.metrics = AgentMetrics()
        self._event_log: List[AgentEvent] = []
        self._created_at = datetime.now(timezone.utc)
        self._last_config: Dict[str, Any] = {}
        self._is_enabled = True

    # --- Lifecycle ---
    
    async def initialize(self):
        """Called once when the agent swarm boots."""
        self._log_event("initialize", "info", f"{self.name} v{self.version} initialized")

    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main execution method. Override in subclasses.
        Returns a result dict with at minimum: { "status": "success"|"error", "summary": str }
        """
        raise NotImplementedError(f"{self.name} must implement execute()")

    async def shutdown(self):
        """Graceful shutdown hook."""
        self._log_event("shutdown", "info", f"{self.name} shutting down")

    # --- Orchestrated Execution w/ Retry ---

    async def run(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Resilient runner with retry, timeout, and metrics collection.
        """
        self.status = AgentStatus.RUNNING
        start = time.monotonic()
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self.execute(context or {}),
                    timeout=self.execution_timeout
                )
                duration = (time.monotonic() - start) * 1000
                self._record_success(duration, result.get("summary"))
                self._log_event("execute", "success", result.get("summary", "OK"), 
                               data=result, duration_ms=duration)
                self.status = AgentStatus.SUCCESS
                return {**result, "duration_ms": round(duration, 2), "attempt": attempt}
            
            except asyncio.TimeoutError:
                last_error = f"Timeout after {self.execution_timeout}s"
                self._log_event("execute", "warning", f"Attempt {attempt} timed out")
            except Exception as e:
                last_error = str(e)
                self._log_event("execute", "error", f"Attempt {attempt} failed: {e}")
            
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay_seconds * attempt)

        # All retries exhausted
        duration = (time.monotonic() - start) * 1000
        self._record_failure(last_error, duration)
        self.status = AgentStatus.FAILED
        return {
            "status": "error",
            "summary": f"All {self.max_retries} attempts failed: {last_error}",
            "duration_ms": round(duration, 2)
        }

    # --- Health ---

    async def health_check(self) -> Dict[str, Any]:
        """Self-diagnostic check."""
        return {
            "agent": self.name,
            "status": self.status.value,
            "enabled": self._is_enabled,
            "uptime_seconds": (datetime.now(timezone.utc) - self._created_at).total_seconds(),
            "metrics": {
                "total": self.metrics.total_executions,
                "success": self.metrics.successful_executions,
                "failed": self.metrics.failed_executions,
                "avg_duration_ms": round(self.metrics.avg_duration_ms, 2),
                "last_execution": self.metrics.last_execution,
            }
        }

    # --- Event Logging ---

    def _log_event(self, action: str, status: str, message: str, 
                   data: Optional[Dict[str, Any]] = None, duration_ms: float = 0.0):
        event = AgentEvent(
            agent_name=self.name,
            action=action,
            status=status,
            message=message,
            data=data or {},
            duration_ms=duration_ms
        )
        self._event_log.append(event)
        # Keep last 200 events only
        if len(self._event_log) > 200:
            self._event_log = self._event_log[-200:]
        
        log_fn = {
            "info": self.logger.info,
            "success": self.logger.info,
            "warning": self.logger.warning,
            "error": self.logger.error,
        }.get(status, self.logger.info)
        log_fn(f"[{self.name}] {action}: {message}")

    def get_recent_events(self, limit: int = 20) -> List[Dict]:
        return [
            {
                "event_id": e.event_id,
                "timestamp": e.timestamp,
                "action": e.action,
                "status": e.status,
                "message": e.message,
                "duration_ms": e.duration_ms,
            }
            for e in reversed(self._event_log[-limit:])
        ]

    # --- Metrics ---

    def _record_success(self, duration_ms: float, summary: Optional[str] = None):
        m = self.metrics
        m.total_executions += 1
        m.successful_executions += 1
        total = m.total_executions
        m.avg_duration_ms = ((m.avg_duration_ms * (total - 1)) + duration_ms) / total
        m.last_execution = datetime.now(timezone.utc).isoformat()
        if summary:
            m.last_execution_summary = summary

    def _record_failure(self, error: Optional[str], duration_ms: float):
        m = self.metrics
        m.total_executions += 1
        m.failed_executions += 1
        m.last_error = error or "Unknown error"
        m.last_execution = datetime.now(timezone.utc).isoformat()

    # --- Serialization ---

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "priority": self.priority.value,
            "icon": self.icon,
            "color": self.color,
            "version": self.version,
            "status": self.status.value,
            "enabled": self._is_enabled,
            "auto_schedule_interval": self.auto_schedule_interval,
            "metrics": {
                "total_executions": self.metrics.total_executions,
                "successful_executions": self.metrics.successful_executions,
                "failed_executions": self.metrics.failed_executions,
                "avg_duration_ms": round(self.metrics.avg_duration_ms, 2),
                "last_execution": self.metrics.last_execution,
                "last_execution_summary": self.metrics.last_execution_summary,
                "last_error": self.metrics.last_error,
            }
        }
