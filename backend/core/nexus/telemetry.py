import time
import logging
from collections import deque
from typing import Dict, Any, List
import asyncio

logger = logging.getLogger("nexus.telemetry")

class NexusTelemetry:
    """
    [Improved Idea] Collects real-time API performance metrics (latency, RPS).
    This refines the existing idea of providing frontend telemetry by replacing hardcoded values
    with actual measured data from the NexusIOGate middleware.
    """
    def __init__(self, window_size_seconds: int = 60):
        self.window_size_seconds = window_size_seconds
        self.requests: deque[float] = deque() # Stores request timestamps
        self.latencies: deque[float] = deque() # Stores request latencies
        self._last_cleanup_time: float = time.time()
        self._lock = asyncio.Lock()

    async def record_request(self, latency_ms: float):
        async with self._lock:
            current_time = time.time()
            self.requests.append(current_time)
            self.latencies.append(latency_ms)
            await self._cleanup_old_data(current_time)

    async def _cleanup_old_data(self, current_time: float):
        # Only cleanup periodically to avoid frequent lock contention
        if current_time - self._last_cleanup_time < 1: # Cleanup every second max
            return
        
        # Remove timestamps older than window_size_seconds
        while self.requests and self.requests[0] < current_time - self.window_size_seconds:
            self.requests.popleft()
            self.latencies.popleft() # Ensure latencies queue matches requests

        self._last_cleanup_time = current_time

    async def get_metrics(self) -> Dict[str, Any]:
        async with self._lock:
            current_time = time.time()
            await self._cleanup_old_data(current_time) # Ensure data is fresh

            requests_in_window = len(self.requests)
            
            # Calculate Requests Per Second (RPS)
            rps = requests_in_window / self.window_size_seconds if self.window_size_seconds > 0 else 0
            
            # Calculate Average Latency
            avg_latency = sum(self.latencies) / requests_in_window if requests_in_window > 0 else 0

            # Calculate P95 Latency [Elite]
            p95_latency = 0
            if requests_in_window > 0:
                sorted_latencies = sorted(list(self.latencies))
                idx = int(requests_in_window * 0.95)
                p95_latency = sorted_latencies[min(idx, requests_in_window - 1)]

            guardian_data = {
                "active_missions": 0,
                "high_risk_missions": 0
            }
            try:
                from guardian_ai.memory_store import guardian_memory
                active_missions = await guardian_memory.get_all_active_missions()
                high_risk = sum(1 for m in active_missions if m.risk_level.name in ["HIGH", "CRITICAL"])
                guardian_data["active_missions"] = len(active_missions)
                guardian_data["high_risk_missions"] = high_risk
            except Exception as e:
                logger.warning(f"Could not fetch Guardian telemetry: {e}")

            return {
                "requests_per_sec": round(rps, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "p95_latency_ms": round(p95_latency, 2),
                "request_count_last_min": requests_in_window,
                "guardian": guardian_data
            }

# Global Singleton
nexus_telemetry = NexusTelemetry()
