"""Rich set of lightweight performance validators used by the automated test suite."""

from __future__ import annotations

import asyncio
import math
from typing import Dict, Iterable, List, Mapping, Sequence


class PerformanceValidator:
    """Simple heuristics to self-validate the routing platform's real-time characteristics."""

    def _percentile(self, latencies: Sequence[float], percentile: float) -> float:
        if not latencies:
            return 0.0
        sorted_vals = sorted(latencies)
        rank = math.ceil(len(sorted_vals) * percentile / 100.0) - 1
        rank = max(0, min(rank, len(sorted_vals) - 1))
        return sorted_vals[rank]

    def validate_large_network_query_latency(self, observed_ms: float, sla_ms: float) -> bool:
        return observed_ms <= sla_ms

    def validate_concurrent_queries_scaling(self, latencies: Sequence[float], p95_threshold_ms: float) -> bool:
        return self._percentile(latencies, 95.0) <= p95_threshold_ms

    def validate_cache_hit_performance(self, latency_ms: float, expected_max_ms: float) -> bool:
        return latency_ms <= expected_max_ms

    def validate_cold_start_performance(self, latency_ms: float, threshold_ms: float) -> bool:
        return latency_ms <= threshold_ms

    def validate_memory_usage_bounded(self, usage_bytes: int, limit_bytes: int) -> bool:
        return usage_bytes <= limit_bytes

    def validate_graph_rebuild_performance(self, duration_ms: float, threshold_ms: float) -> bool:
        return duration_ms <= threshold_ms

    def validate_worst_case_transfers(self, transfers: int, max_allowed_transfers: int) -> bool:
        return transfers <= max_allowed_transfers

    def validate_high_fan_out_station(self, fan_out: int, threshold: int) -> bool:
        return fan_out <= threshold

    def validate_stress_many_routes(
        self,
        total_routes: int,
        total_duration_ms: float,
        per_route_threshold_ms: float,
    ) -> bool:
        if total_routes <= 0:
            return False
        avg = total_duration_ms / total_routes
        return avg <= per_route_threshold_ms

    def validate_timeout_handling(self, timed_out: bool, expected_to_timeout: bool) -> bool:
        return timed_out == expected_to_timeout

    def validate_query_cancellation_support(self, task: asyncio.Task) -> bool:
        return getattr(task, "cancelled", lambda: False)()

    def validate_async_concurrency_correctness(self, results: Sequence, expected: Sequence) -> bool:
        return list(results) == list(expected)

    def validate_cpu_spike_resilience(self, samples: Iterable[float], threshold_percent: float) -> bool:
        samples_list = list(samples)
        max_usage = max(samples_list) if samples_list else 0.0
        return max_usage <= threshold_percent

    def validate_rate_limiting_behavior(
        self,
        observed_requests: int,
        allowed: int,
        observed_429: int = 0,
    ) -> bool:
        if observed_requests > allowed and observed_429 == 0:
            return False
        return True

    def validate_batch_query_efficiency(
        self,
        batch_size: int,
        total_ms: float,
        per_item_threshold_ms: float,
    ) -> bool:
        if batch_size <= 0:
            return False
        avg_per_item = total_ms / batch_size
        return avg_per_item <= per_item_threshold_ms

    def validate_incremental_update_speed(
        self,
        changed_items: int,
        duration_ms: float,
        threshold_ms: float,
    ) -> bool:
        if changed_items <= 0:
            return False
        avg_per_item = duration_ms / changed_items
        return avg_per_item <= threshold_ms

    def validate_multi_tenant_load_isolation(
        self,
        tenants: Mapping[str, float],
        isolation_multiplier: float,
    ) -> bool:
        if not tenants:
            return True
        values = list(tenants.values())
        min_usage = min(values)
        max_usage = max(values)
        if min_usage <= 0:
            return False
        return (max_usage / min_usage) <= isolation_multiplier

    def validate_cache_eviction_correctness(
        self,
        before: Sequence[str],
        after: Sequence[str],
        evicted: Sequence[str],
    ) -> bool:
        before_set = set(before)
        after_set = set(after)
        evicted_set = set(evicted)
        return (
            after_set.issubset(before_set)
            and evicted_set.issubset(before_set)
            and evicted_set.isdisjoint(after_set)
        )

    def validate_memory_leak_detection(
        self,
        samples: Sequence[float],
        allowed_growth_bytes: float,
    ) -> bool:
        if not samples:
            return True
        growth = samples[-1] - samples[0]
        return growth <= allowed_growth_bytes

    def validate_sla_monitoring_metrics(self, metrics: Dict[str, float]) -> bool:
        p50 = metrics.get("p50", math.inf)
        p95 = metrics.get("p95", math.inf)
        error_rate = metrics.get("error_rate", 0.0)
        return p50 <= p95 and error_rate <= 0.05
