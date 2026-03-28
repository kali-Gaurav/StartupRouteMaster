import time
import asyncio
from typing import Dict, Any, Optional
import logging
from core.resource_monitor import resource_monitor
from core.system_monitor import system_monitor

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
    Refactored for Task 2: Resource-Aware Global Monitor.
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
        self._last_surge_level = SurgeLevel.NORMAL
        self._surge_override: Optional[SurgeLevel] = None 
        self.start_time = time.time()
        
        # [Task 25] Provider Failover Metrics
        self.provider_calls: Dict[str, int] = {"rapidapi": 0, "ntes_scraper": 0, "fallback": 0}
        self.provider_failures: Dict[str, int] = {"rapidapi": 0, "ntes_scraper": 0, "fallback": 0}
        self.provider_latency_sum: Dict[str, float] = {"rapidapi": 0.0, "ntes_scraper": 0.0}

    @property
    def cpu_usage_percent(self) -> float:
        """[Task 29] Get CPU from central monitor."""
        # Fix: Access the nested dictionary correctly
        return system_monitor.stats.get("resource", {}).get("cpu_current", 0.0)

    @property
    def ram_usage_percent(self) -> float:
        """[Task 29] Get RAM from central monitor."""
        return system_monitor.stats.get("resource", {}).get("ram_percent", 0.0)

    @property
    def surge_level(self):
        """Task 4: Delegates to centralized system_monitor state."""
        return system_monitor.current_state

    def get_report(self) -> Dict[str, Any]:
        uptime = time.time() - self.start_time
        accuracy = 0.0
        if (self.correct_predictions + self.false_positives) > 0:
            accuracy = self.correct_predictions / (self.correct_predictions + self.false_positives)

        stats = resource_monitor.get_stats()
        return {
            "uptime_seconds": uptime,
            "performance": {
                "surge_level": self.surge_level.name,
                "event_loop_latency_ms": round(self.event_loop_latency_ms, 4),
                "cpu_usage_percent": round(self.cpu_usage_percent, 2), # Use property
                "ram_usage_percent": round(self.ram_usage_percent, 2), # Use property
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
            },
            "providers": {
                "calls": self.provider_calls,
                "failures": self.provider_failures,
                "avg_latency": {
                    k: round(v / max(1, self.provider_calls.get(k, 1)), 2)
                    for k, v in self.provider_latency_sum.items()
                }
            }
        }

    def record_provider_call(self, provider: str, success: bool, latency_ms: float = 0.0):
        """[Task 25] Unified provider metrics telemetry."""
        p = provider.lower()
        if p not in self.provider_calls: 
            self.provider_calls[p] = 0
            self.provider_failures[p] = 0
            
        self.provider_calls[p] += 1
        if not success:
            self.provider_failures[p] += 1
        
        if p in self.provider_latency_sum:
            self.provider_latency_sum[p] += latency_ms

    def get_adaptive_timeout(self, base_timeout: float = 30.0) -> float:
        latency_factor = 1.0
        if self.event_loop_latency_ms > 50:
            latency_factor = 0.5 
        elif self.event_loop_latency_ms > 20:
            latency_factor = 0.8
            
        cpu_factor = 1.0
        if self.cpu_usage_percent > 90:
            cpu_factor = 0.5
            
        final_timeout = base_timeout * latency_factor * cpu_factor
        return max(2.0, final_timeout)

    @property
    def is_overloaded(self) -> bool:
        return (
            self.event_loop_latency_ms > 100 or 
            self.cpu_usage_percent > 95 or 
            self.ram_usage_percent > 95
        )

    # [Task 13.8] Performance Heatmaps
    async def record_latency(self, endpoint: str, duration_ms: float):
        """Records latency into Redis buckets (Histogram)."""
        from services.multi_layer_cache import multi_layer_cache
        if not multi_layer_cache.redis: return
        
        # Buckets: 50ms, 100ms, 250ms, 500ms, 1s, 2s, 5s+
        buckets = [50, 100, 250, 500, 1000, 2000, 5000]
        selected_bucket = "inf"
        for b in buckets:
            if duration_ms <= b:
                selected_bucket = str(b)
                break
        
        try:
            key = f"metrics:heatmap:{endpoint}"
            await multi_layer_cache.redis.hincrby(key, selected_bucket, 1)
            # Add to a global SLA counter [13.9]
            if duration_ms > 2000:
                await multi_layer_cache.redis.incr(f"metrics:sla_violations:{endpoint}")
        except Exception: pass

class DegradationManager:
    @staticmethod
    def should_skip_heavy_expansion() -> bool:
        return jit_metrics.cpu_usage_percent > 80 or jit_metrics.event_loop_latency_ms > 50

    @staticmethod
    def should_skip_ml_prediction() -> bool:
        return jit_metrics.ram_usage_percent > 90 or jit_metrics.cpu_usage_percent > 85

jit_metrics = TelemetryMetrics()

async def run_event_loop_monitor():
    logger.info("⏱️ Event Loop Monitor Started.")
    while True:
        start = time.perf_counter()
        await asyncio.sleep(0.1) 
        actual_delay = (time.perf_counter() - start - 0.1) * 1000 
        
        jit_metrics.event_loop_latency_ms = (0.8 * jit_metrics.event_loop_latency_ms) + (0.2 * max(0, actual_delay))
        system_monitor.update_loop_latency(actual_delay)
        await asyncio.sleep(0.5)

