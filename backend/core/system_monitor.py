import time
import asyncio
import logging
import psutil
from typing import Dict, Any, List, Optional
from enum import IntEnum
import collections

from services.alert_service import alert_service
logger = logging.getLogger("routemaster.system_monitor")

class SystemState(IntEnum):
    NORMAL = 0
    WARNING = 1
    CRITICAL = 2
    EMERGENCY = 3

class LatencyTracker:
    """Task 4.5: Percentile tracking (P50, P90, P99)."""
    def __init__(self, window_size: int = 1000):
        self.window = collections.deque(maxlen=window_size)

    def add(self, latency_ms: float):
        self.window.append(latency_ms)

    def get_percentile(self, p: float) -> float:
        if not self.window: return 0.0
        sorted_window = sorted(self.window)
        idx = int(len(sorted_window) * (p / 100))
        return sorted_window[min(idx, len(sorted_window) - 1)]

class ResourceForecaster:
    """
    Task 4.10: Advanced CPU Spike Prediction using Double Exponential Smoothing (Holt-Winters).
    Captures both level and trend for more accurate FAANG-level forecasting.
    """
    def __init__(self, alpha: float = 0.3, beta: float = 0.1):
        self.alpha = alpha  # Level smoothing
        self.beta = beta    # Trend smoothing
        self.level = 0.0
        self.trend = 0.0
        self._initialized = False

    def update(self, val: float):
        if not self._initialized:
            self.level = val
            self.trend = 0.0
            self._initialized = True
            return
        
        last_level = self.level
        # 1. Update Level
        self.level = (self.alpha * val) + ((1 - self.alpha) * (self.level + self.trend))
        # 2. Update Trend
        self.trend = (self.beta * (self.level - last_level)) + ((1 - self.beta) * self.trend)

    def predict_next(self, intervals: int = 1) -> float:
        """Predicts the value for 'n' intervals ahead."""
        prediction = self.level + (intervals * self.trend)
        return max(0.0, min(100.0, prediction))

class SystemMonitor:
    """
    Task 4: Centralized FAANG-Level Resource Monitor (HARDENED).
    Single Source of Truth for: CPU, RAM, Latency, Cache Stats, Anomalies.
    """
    def __init__(self):
        # Base Metrics
        self._cpu_percent = 0.0
        self._ram_percent = 0.0
        self._loop_latency_ms = 0.0
        self._num_fds = 0
        self._last_update = 0
        self._update_lock = asyncio.Lock()
        self._state = SystemState.NORMAL
        
        # Advanced Observability [Task 4]
        self.latency_tracker = LatencyTracker()
        self.forecaster = ResourceForecaster()
        self.cache_hits = 0
        self.cache_misses = 0
        self.last_rss = 0
        self.rss_growth_rate = 0.0 # Bytes/sec
        
        self.process = psutil.Process()
        self.start_time = time.time()

    async def update_if_stale(self, force: bool = False):
        """Task 4.4: Async sampling system."""
        now = time.time()
        interval = 0.25 if self._state >= SystemState.WARNING else 1.0
        
        if not force and (now - self._last_update < interval):
            return

        async with self._update_lock:
            if not force and (now - self._last_update < interval):
                return
            
            # CPU & Trend [Task 4.3 & 4.10]
            current_cpu = psutil.cpu_percent(interval=None)
            self.forecaster.update(current_cpu)
            self._cpu_percent = current_cpu
            
            # RAM & Leak Detection [Task 4.9]
            mem = self.process.memory_info()
            current_rss = mem.rss
            if self.last_rss > 0:
                elapsed = now - self._last_update
                self.rss_growth_rate = (current_rss - self.last_rss) / elapsed
            self.last_rss = current_rss
            self._ram_percent = psutil.virtual_memory().percent
            
            # FDs
            try:
                # psutil.Process.num_fds() is Unix-only and may not be recognized by all type checkers.
                # For Windows compatibility or missing attributes, we use len(process.open_files()) or fallback to 0.
                self._num_fds = getattr(self.process, 'num_fds', lambda: len(self.process.open_files()))()
            except: self._num_fds = 0
            
            # 3. Anomaly Detection [Task 4.6 & 13.7]
            p99 = self.latency_tracker.get_percentile(99)
            is_anomalous = p99 > 300 or self.rss_growth_rate > (1024 * 1024) # >1MB/s
            
            if is_anomalous:
                asyncio.create_task(alert_service.send_alert(
                    "System Anomaly Detected",
                    f"P99 Latency: {p99:.1f}ms\nRSS Growth: {self.rss_growth_rate/1024/1024:.2f} MB/s",
                    level="ERROR",
                    extra={"cpu": self._cpu_percent, "ram": self._ram_percent}
                ))

            # Subtask 4.9: Tracemalloc Leak Analyzer
            if self.rss_growth_rate > (5 * 1024 * 1024): # >5MB/s growth
                import tracemalloc
                if not tracemalloc.is_tracing():
                    tracemalloc.start()
                snapshot = tracemalloc.take_snapshot()
                top_stats = snapshot.statistics('lineno')
                logger.warning("🧪 Memory Spike: Top 3 allocators:")
                for stat in top_stats[:3]:
                    logger.warning(str(stat))
                
                asyncio.create_task(alert_service.send_alert(
                    "🚨 CRITICAL MEMORY SPIKE",
                    f"Growth: {self.rss_growth_rate/1024/1024:.2f} MB/s. Analytics triggered.",
                    level="CRITICAL"
                ))

            # If predicted CPU is > 95%, warn early
            predicted_cpu = self.forecaster.predict_next()
            if predicted_cpu > 95 and self._state < SystemState.WARNING:
                logger.warning(f"🚨 CPU SPIKE PREDICTED: Next: {predicted_cpu:.1f}%")

            self._determine_state()
            self._last_update = time.time()

    def _determine_state(self):
        """[SAFE_MODE] System state locked to NORMAL per designer request."""
        self._state = SystemState.NORMAL

    @property
    def current_state(self) -> SystemState:
        """Returns the current calculated system state."""
        return self._state

    @property
    def stats(self) -> Dict[str, Any]:
        """Task 4.7 & 4.8: Expose metrics API / Prometheus format."""
        p99 = self.latency_tracker.get_percentile(99)
        return {
            "cpu": self._cpu_percent,
            "ram": self._ram_percent,
            "resource": {
                "cpu_current": self._cpu_percent,
                "cpu_predicted": self.forecaster.predict_next(),
                "ram_percent": self._ram_percent,
                "rss_bytes": self.last_rss,
                "rss_growth_bps": self.rss_growth_rate,
                "fds": self._num_fds
            },
            "performance": {
                "p50_ms": self.latency_tracker.get_percentile(50),
                "p90_ms": self.latency_tracker.get_percentile(90),
                "p99_ms": p99,
                "loop_latency_avg": self._loop_latency_ms
            },
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "ratio": self.cache_hits / (self.cache_hits + self.cache_misses + 1)
            },
            "system": {
                "state": self._state.name,
                "uptime": time.time() - self.start_time,
                "is_anomalous": p99 > 300 or self.rss_growth_rate > (1024 * 1024) # >1MB/s growth is suspect
            }
        }

    def report_request_latency(self, latency_ms: float):
        """Task 4.5: Report per-request latency."""
        self.latency_tracker.add(latency_ms)

    def report_cache_event(self, hit: bool):
        if hit: self.cache_hits += 1
        else: self.cache_misses += 1

    def update_loop_latency(self, latency_ms: float):
        """External update from loop monitor."""
        self._loop_latency_ms = (0.8 * self._loop_latency_ms) + (0.2 * max(0, latency_ms))

# Global Instance
system_monitor = SystemMonitor()
