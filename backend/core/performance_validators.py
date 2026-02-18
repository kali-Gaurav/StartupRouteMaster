"""
Performance & Scalability Validators (RT-091 — RT-110)

Each method implements a small, deterministic check that returns True when the
corresponding performance requirement passes and False when it fails. These are
intended for unit / integration tests and lightweight runtime assertions.

The validators are intentionally conservative and fast so they can be used in
hot paths for health checks or in unit tests that assert SLAs.
"""
from typing import Dict, Iterable, List
import asyncio
import statistics


class PerformanceValidator:
    """Validator helpers for performance & scalability requirements (RT-091 → RT-110)."""

    # RT-091 — Large network query (< SLA time)
    def validate_large_network_query_latency(self, observed_ms: float, sla_ms: float) -> bool:
        """Return True when observed latency is within SLA (milliseconds)."""
        return float(observed_ms) <= float(sla_ms)

    # RT-092 — Concurrent queries scaling (basic P95 check)
    def validate_concurrent_queries_scaling(self, latencies_ms: Iterable[float], p95_threshold_ms: float) -> bool:
        """Compute P95 and ensure it is below threshold."""
        samples = sorted(float(x) for x in latencies_ms)
        if not samples:
            return True
        # simple percentile implementation
        idx = min(len(samples) - 1, int(round(0.95 * (len(samples) - 1))))
        p95 = samples[idx]
        return p95 <= float(p95_threshold_ms)

    # RT-093 — Cache hit performance
    def validate_cache_hit_performance(self, cache_latency_ms: float, expected_max_ms: float) -> bool:
        return float(cache_latency_ms) <= float(expected_max_ms)

    # RT-094 — Cold start performance
    def validate_cold_start_performance(self, startup_ms: float, threshold_ms: float) -> bool:
        return float(startup_ms) <= float(threshold_ms)

    # RT-095 — Memory usage bounded
    def validate_memory_usage_bounded(self, memory_bytes: int, limit_bytes: int) -> bool:
        return int(memory_bytes) <= int(limit_bytes)

    # RT-096 — Graph rebuild performance
    def validate_graph_rebuild_performance(self, rebuild_ms: float, threshold_ms: float) -> bool:
        return float(rebuild_ms) <= float(threshold_ms)

    # RT-097 — Worst-case transfers scenario
    def validate_worst_case_transfers(self, num_transfers: int, max_allowed_transfers: int = 20) -> bool:
        return int(num_transfers) <= int(max_allowed_transfers)

    # RT-098 — High fan-out stations
    def validate_high_fan_out_station(self, neighbor_count: int, threshold: int = 500) -> bool:
        return int(neighbor_count) <= int(threshold)

    # RT-099 — Stress test with many routes (per-route overhead check)
    def validate_stress_many_routes(self, route_count: int, total_duration_ms: float, per_route_threshold_ms: float) -> bool:
        if route_count <= 0:
            return True
        per_route = float(total_duration_ms) / float(route_count)
        return per_route <= float(per_route_threshold_ms)

    # RT-100 — Timeout handling
    def validate_timeout_handling(self, timed_out: bool, expected_to_timeout: bool = False) -> bool:
        """Return True when timeout behavior matches expectation."""
        return bool(timed_out) == bool(expected_to_timeout)

    # RT-101 — Query cancellation support (accepts a Task/Future)
    def validate_query_cancellation_support(self, fut: asyncio.Future, timeout: float = 0.1) -> bool:
        """Try cancelling `fut` and assert it becomes cancelled within `timeout` seconds."""
        if fut.done():
            return fut.cancelled()
        fut.cancel()
        try:
            # allow event loop to process cancellation
            loop = asyncio.get_event_loop()
            loop.run_until_complete(asyncio.sleep(timeout))
        except Exception:
            # if running inside a running loop this will raise; fall back to check
            pass
        return fut.cancelled()

    # RT-102 — Async concurrency correctness (basic barrier/check)
    def validate_async_concurrency_correctness(self, results: List, expected: List) -> bool:
        return sorted(results) == sorted(expected)

    # RT-103 — CPU spike resilience (simple max sample check)
    def validate_cpu_spike_resilience(self, cpu_percent_samples: Iterable[float], threshold_percent: float) -> bool:
        samples = list(float(x) for x in cpu_percent_samples)
        if not samples:
            return True
        return max(samples) <= float(threshold_percent)

    # RT-104 — Rate limiting behavior (observed_429 should be > 0 when limit exceeded)
    def validate_rate_limiting_behavior(self, observed_requests: int, allowed: int, observed_429: int) -> bool:
        if observed_requests <= allowed:
            return observed_429 == 0
        return observed_429 > 0

    # RT-105 — Batch query efficiency (per-item overhead)
    def validate_batch_query_efficiency(self, batch_size: int, total_ms: float, per_item_threshold_ms: float) -> bool:
        if batch_size <= 0:
            return True
        return (float(total_ms) / float(batch_size)) <= float(per_item_threshold_ms)

    # RT-106 — Incremental update speed
    def validate_incremental_update_speed(self, changed_items: int, duration_ms: float, threshold_ms: float) -> bool:
        if changed_items <= 0:
            return True
        per_item = float(duration_ms) / float(changed_items)
        return per_item <= float(threshold_ms)

    # RT-107 — Multi-tenant load isolation (per-tenant latencies should not exceed multiplier)
    def validate_multi_tenant_load_isolation(self, tenant_latencies_ms: Dict[str, float], isolation_multiplier: float = 3.0) -> bool:
        if not tenant_latencies_ms:
            return True
        vals = list(tenant_latencies_ms.values())
        median = statistics.median(vals)
        # no tenant should be > median * multiplier
        return all(v <= median * isolation_multiplier for v in vals)

    # RT-108 — Cache eviction correctness (basic set membership tests)
    def validate_cache_eviction_correctness(self, before_keys: Iterable[str], after_keys: Iterable[str], evicted_keys: Iterable[str]) -> bool:
        after_set = set(after_keys)
        for k in evicted_keys:
            if k in after_set:
                return False
        return True

    # RT-109 — Memory leak detection (ensure growth within budget)
    def validate_memory_leak_detection(self, memory_samples_bytes: Iterable[int], allowed_growth_bytes: int) -> bool:
        samples = list(int(x) for x in memory_samples_bytes)
        if len(samples) < 2:
            return True
        growth = samples[-1] - samples[0]
        return growth <= int(allowed_growth_bytes)

    # RT-110 — SLA monitoring metrics presence & sanity
    def validate_sla_monitoring_metrics(self, metrics: Dict[str, float]) -> bool:
        required = {"p50", "p95", "error_rate"}
        if not required.issubset(set(metrics.keys())):
            return False
        try:
            p50 = float(metrics["p50"])
            p95 = float(metrics["p95"])
            err = float(metrics["error_rate"])
        except Exception:
            return False
        return p50 >= 0 and p95 >= p50 and 0.0 <= err <= 1.0


__all__ = ["PerformanceValidator"]
