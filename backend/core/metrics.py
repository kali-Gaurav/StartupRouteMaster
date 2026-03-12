import time
import asyncio
import psutil
from typing import Dict, Any
import logging

logger = logging.getLogger("jit-metrics")

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
        self.start_time = time.time()

    def get_report(self) -> Dict[str, Any]:
        uptime = time.time() - self.start_time
        accuracy = 0.0
        if (self.correct_predictions + self.false_positives) > 0:
            accuracy = self.correct_predictions / (self.correct_predictions + self.false_positives)

        return {
            "uptime_seconds": uptime,
            "performance": {
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
