import time
import asyncio
import psutil
from typing import Dict, Any
import logging

logger = logging.getLogger("jit-metrics")

from enum import IntEnum

class SurgeLevel(IntEnum):
    NORMAL = 0
    ELEVATED = 1
    HIGH = 2
    CRITICAL = 3

class TelemetryMetrics:
    """
    Prometheus-style Metrics for Predictive JIT and System Health.
    """
    def __init__(self):
        self.predictions_total = 0
        self.correct_predictions = 0
        self.false_positives = 0
        self.sla_violations = 0
        self.total_hydrations = 0
        self.prewarms_triggered = 0
        self.prewarms_skipped = 0
        self.ml_inferences_total = 0
        self.ml_latency_avg_ms = 0.0
        self.ml_batch_efficiency = 0.0
        self.reaper_events = 0
        self.event_loop_latency_ms = 0.0
        self.cpu_usage_percent = 0.0
        self.ram_usage_percent = 0.0
        self._last_surge_level = SurgeLevel.NORMAL
        self._surge_override: Optional[SurgeLevel] = None # Subtask 4.6 testing
        self.start_time = time.time()

    @property
    def surge_level(self) -> SurgeLevel:
        """
        Subtask 4.2: Dynamic Surge Level Calculation.
        Uses multiple metrics with hysteresis to prevent rapid state flapping.
        """
        # [4.6 Override for testing]
        if hasattr(self, '_surge_override') and self._surge_override is not None:
            return self._surge_override

        cpu = self.cpu_usage_percent
        ram = self.ram_usage_percent
        latency = self.event_loop_latency_ms

        # Determine raw level
        raw_level = SurgeLevel.NORMAL
        if cpu > 95 or ram > 95 or latency > 200:
            raw_level = SurgeLevel.CRITICAL
        elif cpu > 85 or ram > 90 or latency > 100:
            raw_level = SurgeLevel.HIGH
        elif cpu > 70 or ram > 80 or latency > 50:
            raw_level = SurgeLevel.ELEVATED

        # Hysteresis: only downgrade if we are well below the threshold
        # (Prevent flip-flopping)
        if raw_level < self._last_surge_level:
            # Check if we are really clear of the previous threshold
            # We need to be 5% below the trigger to downgrade
            is_still_high = False
            if self._last_surge_level == SurgeLevel.CRITICAL:
                is_still_high = cpu > 90 or ram > 90 or latency > 150
            elif self._last_surge_level == SurgeLevel.HIGH:
                is_still_high = cpu > 80 or ram > 85 or latency > 80
            elif self._last_surge_level == SurgeLevel.ELEVATED:
                is_still_high = cpu > 65 or ram > 75 or latency > 40
            
            if is_still_high:
                return self._last_surge_level

        self._last_surge_level = raw_level
        return raw_level

    def get_report(self) -> Dict[str, Any]:
        uptime = time.time() - self.start_time
        accuracy = 0.0
        if (self.correct_predictions + self.false_positives) > 0:
            accuracy = self.correct_predictions / (self.correct_predictions + self.false_positives)

        return {
            "uptime_seconds": uptime,
            "performance": {
                "surge_level": self.surge_level.name,
                "event_loop_latency_ms": round(self.event_loop_latency_ms, 4),
                "cpu_usage_percent": round(self.cpu_usage_percent, 2),
                "ram_usage_percent": round(self.ram_usage_percent, 2),
                "reaper_events": self.reaper_events
            },
            "predictions": {
                "total": self.predictions_total,
                "correct": self.correct_predictions,
                "false_positives": self.false_positives,
                "accuracy": round(accuracy, 4),
                "sla_violations": self.sla_violations
            },
            "ml_engine": {
                "inferences": self.ml_inferences_total,
                "avg_latency_ms": round(self.ml_latency_avg_ms, 4),
                "batch_efficiency": round(self.ml_batch_efficiency, 4)
            },
            "flow": {
                "hydrations": self.total_hydrations,
                "prewarms_triggered": self.prewarms_triggered,
                "prewarms_skipped": self.prewarms_skipped
            }
        }

    def get_adaptive_timeout(self, base_timeout: float = 30.0) -> float:
        """
        Subtask 1.3: Adaptive Timeout Logic.
        Reduces timeout dynamically as system load increases.
        """
        # If latency is high (>50ms), start cutting timeout
        latency_factor = 1.0
        if self.event_loop_latency_ms > 50:
            latency_factor = 0.5 # Half the timeout if loop is struggling
        elif self.event_loop_latency_ms > 20:
            latency_factor = 0.8
            
        # If CPU is very high, cut further
        cpu_factor = 1.0
        if self.cpu_usage_percent > 90:
            cpu_factor = 0.5
            
        final_timeout = base_timeout * latency_factor * cpu_factor
        return max(2.0, final_timeout) # Minimum 2 seconds

    @property
    def is_overloaded(self) -> bool:
        """
        Subtask 1.4: Global Overload Signal.
        Returns True if the system is hitting critical VPS resource limits.
        """
        return (
            self.event_loop_latency_ms > 100 or 
            self.cpu_usage_percent > 95 or 
            self.ram_usage_percent > 95
        )

class DegradationManager:
    """
    Subtask 1.11: Graceful Degradation Manager.
    Decides which features to disable based on real-time load.
    """
    @staticmethod
    def should_skip_heavy_expansion() -> bool:
        # If CPU > 80% or Latency > 50ms, skip multi-day expansion
        return jit_metrics.cpu_usage_percent > 80 or jit_metrics.event_loop_latency_ms > 50

    @staticmethod
    def should_skip_ml_prediction() -> bool:
        # If RAM is tight or CPU is high, skip ML
        return jit_metrics.ram_usage_percent > 90 or jit_metrics.cpu_usage_percent > 85

# Global Instance
jit_metrics = TelemetryMetrics()

async def run_event_loop_monitor():
    """
    Subtask 1.1: Event Loop Latency Monitor.
    Measures the 'lag' in the event loop by timing how long asyncio.sleep(0.1) actually takes.
    """
    logger.info("⏱️ Event Loop Monitor Started.")
    while True:
        start = time.perf_counter()
        await asyncio.sleep(0.1) 
        actual_delay = (time.perf_counter() - start - 0.1) * 1000 
        
        jit_metrics.event_loop_latency_ms = (0.8 * jit_metrics.event_loop_latency_ms) + (0.2 * max(0, actual_delay))
        await asyncio.sleep(0.5)

async def run_hardware_monitor():
    """
    Subtask 1.2: Hardware Monitor.
    Samples CPU and RAM usage to drive load-shedding logic.
    """
    logger.info("🖥️ Hardware Monitor Started.")
    # Initialize CPU sampling
    psutil.cpu_percent(interval=None)
    
    while True:
        try:
            jit_metrics.cpu_usage_percent = psutil.cpu_percent(interval=None)
            jit_metrics.ram_usage_percent = psutil.virtual_memory().percent
            
            if jit_metrics.cpu_usage_percent > 90 or jit_metrics.ram_usage_percent > 90:
                logger.warning(f"⚠️ High Resource Usage: CPU {jit_metrics.cpu_usage_percent}% | RAM {jit_metrics.ram_usage_percent}%")
                
        except Exception as e:
            logger.error(f"Hardware Monitor Error: {e}")
            
        await asyncio.sleep(1.0)
