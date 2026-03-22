import time
import logging
from enum import IntEnum
from typing import Dict, Any, Optional
from core.resource_monitor import resource_monitor
from core.metrics import jit_metrics

logger = logging.getLogger("routemaster.state_manager")

class SystemState(IntEnum):
    NORMAL = 0
    WARNING = 1
    CRITICAL = 2

class SystemStateManager:
    """
    Unified System State Manager.
    Consolidates resource monitoring and decision making into a single engine.
    """
    def __init__(self):
        self._last_state = SystemState.NORMAL
        self._state_history = []
        self._last_check_time = 0
        self._check_interval = 1.0 # 1 second for high-res monitoring

    def get_current_state(self) -> Dict[str, Any]:
        """
        Calculates the unified system state based on all metrics.
        """
        stats = resource_monitor.get_stats()
        cpu = stats.get("cpu_percent", 0.0)
        ram = stats.get("ram_percent", 0.0)
        latency = jit_metrics.event_loop_latency_ms
        fds = stats.get("num_fds", 0)

        # 1. Determine Base State
        state = SystemState.NORMAL
        
        # Critical Thresholds
        if cpu > 90 or ram > 85 or latency > 200 or fds > 800:
            state = SystemState.CRITICAL
        # Warning Thresholds
        elif cpu > 70 or ram > 75 or latency > 50 or fds > 500:
            state = SystemState.WARNING

        # 2. Hysteresis (Prevent state flapping)
        if state < self._last_state:
            # Only downgrade state if metrics are significantly lower
            is_still_strained = False
            if self._last_state == SystemState.CRITICAL:
                is_still_strained = cpu > 85 or ram > 80 or latency > 150
            elif self._last_state == SystemState.WARNING:
                is_still_strained = cpu > 65 or ram > 70 or latency > 40
            
            if is_still_strained:
                state = self._last_state

        self._last_state = state

        # 3. Decision Matrix (Recommendations)
        recommendations = {
            "allow_heavy": state != SystemState.CRITICAL,
            "allow_standard": True, # Usually always True unless extreme
            "shed_load": state == SystemState.CRITICAL,
            "throttle_search": state != SystemState.NORMAL,
            "compression_level": 1 if state != SystemState.NORMAL else 4,
            "cache_only": state == SystemState.CRITICAL,
            "timeout_factor": 0.5 if state == SystemState.CRITICAL else 0.8 if state == SystemState.WARNING else 1.0
        }

        return {
            "state": state.name,
            "level": int(state),
            "metrics": {
                "cpu": cpu,
                "ram": ram,
                "latency_ms": latency,
                "fds": fds
            },
            "recommendations": recommendations,
            "timestamp": time.time()
        }

    def get_health_report(self) -> Dict[str, Any]:
        state_info = self.get_current_state()
        return {
            "status": state_info["state"],
            "metrics": state_info["metrics"],
            "healthy": state_info["level"] != int(SystemState.CRITICAL)
        }

# Global Instance
state_manager = SystemStateManager()
