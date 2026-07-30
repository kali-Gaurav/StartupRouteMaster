import asyncio
import pytest

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "perf_mod",
    Path("backend/core/performance_validators.py").resolve()
)
_perf_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_perf_mod)
PerformanceValidator = _perf_mod.PerformanceValidator

pv = PerformanceValidator()


def test_rt_091_large_network_query_latency():
    assert pv.validate_large_network_query_latency(80.0, sla_ms=200.0)
    assert not pv.validate_large_network_query_latency(250.0, sla_ms=200.0)


def test_rt_092_concurrent_queries_scaling_p95():
    latencies = [10, 12, 15, 20, 30, 40, 120, 200]
    assert pv.validate_concurrent_queries_scaling(latencies, p95_threshold_ms=220)
    assert not pv.validate_concurrent_queries_scaling(latencies, p95_threshold_ms=50)


def test_rt_093_cache_hit_performance():
    assert pv.validate_cache_hit_performance(5.0, expected_max_ms=20.0)
    assert not pv.validate_cache_hit_performance(30.0, expected_max_ms=20.0)


def test_rt_094_cold_start_performance():
    assert pv.validate_cold_start_performance(250.0, threshold_ms=500.0)
    assert not pv.validate_cold_start_performance(1200.0, threshold_ms=500.0)


def test_rt_095_memory_usage_bounded():
    assert pv.validate_memory_usage_bounded(150_000_000, limit_bytes=200_000_000)
    assert not pv.validate_memory_usage_bounded(250_000_000, limit_bytes=200_000_000)


def test_rt_096_graph_rebuild_performance():
    assert pv.validate_graph_rebuild_performance(800.0, threshold_ms=1500.0)
    assert not pv.validate_graph_rebuild_performance(2000.0, threshold_ms=1500.0)


def test_rt_097_worst_case_transfers():
    assert pv.validate_worst_case_transfers(3, max_allowed_transfers=10)
    assert not pv.validate_worst_case_transfers(25, max_allowed_transfers=10)


def test_rt_098_high_fan_out_station():
    assert pv.validate_high_fan_out_station(100, threshold=500)
    assert not pv.validate_high_fan_out_station(600, threshold=500)


def test_rt_099_stress_many_routes():
    assert pv.validate_stress_many_routes(1000, total_duration_ms=5000.0, per_route_threshold_ms=10.0)
    assert not pv.validate_stress_many_routes(1000, total_duration_ms=50000.0, per_route_threshold_ms=10.0)


def test_rt_100_timeout_handling():
    assert pv.validate_timeout_handling(True, expected_to_timeout=True)
    assert pv.validate_timeout_handling(False, expected_to_timeout=False)
    assert not pv.validate_timeout_handling(True, expected_to_timeout=False)


@pytest.mark.asyncio
async def test_rt_101_query_cancellation_support():
    # create a running task then cancel it and validate
    t = asyncio.create_task(asyncio.sleep(5))
    await asyncio.sleep(0)  # let task start
    t.cancel()
    await asyncio.sleep(0)  # process cancellation
    assert t.cancelled()
    assert pv.validate_query_cancellation_support(t)


@pytest.mark.asyncio
async def test_rt_102_async_concurrency_correctness():
    async def worker(i):
        await asyncio.sleep(0)
        return i

    tasks = [worker(i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    assert pv.validate_async_concurrency_correctness(results, list(range(10)))


def test_rt_103_cpu_spike_resilience():
    assert pv.validate_cpu_spike_resilience([10, 20, 30, 40], threshold_percent=80)
    assert not pv.validate_cpu_spike_resilience([10, 20, 90, 100], threshold_percent=80)


def test_rt_104_rate_limiting_behavior():
    assert pv.validate_rate_limiting_behavior(observed_requests=50, allowed=100, observed_429=0)
    assert pv.validate_rate_limiting_behavior(observed_requests=200, allowed=100, observed_429=5)
    assert not pv.validate_rate_limiting_behavior(observed_requests=200, allowed=100, observed_429=0)


def test_rt_105_batch_query_efficiency():
    assert pv.validate_batch_query_efficiency(batch_size=100, total_ms=200.0, per_item_threshold_ms=5.0)
    assert not pv.validate_batch_query_efficiency(batch_size=100, total_ms=1000.0, per_item_threshold_ms=5.0)


def test_rt_106_incremental_update_speed():
    assert pv.validate_incremental_update_speed(changed_items=50, duration_ms=500.0, threshold_ms=20.0)
    assert not pv.validate_incremental_update_speed(changed_items=50, duration_ms=2000.0, threshold_ms=20.0)


def test_rt_107_multi_tenant_load_isolation():
    tenants = {"a": 10.0, "b": 12.0, "c": 15.0}
    assert pv.validate_multi_tenant_load_isolation(tenants, isolation_multiplier=3.0)
    tenants_bad = {"a": 10.0, "b": 1000.0}
    assert not pv.validate_multi_tenant_load_isolation(tenants_bad, isolation_multiplier=3.0)


def test_rt_108_cache_eviction_correctness():
    before = ["k1", "k2", "k3"]
    after = ["k1"]
    evicted = ["k2", "k3"]
    assert pv.validate_cache_eviction_correctness(before, after, evicted)
    # if evicted key still present -> fail
    assert not pv.validate_cache_eviction_correctness(before, ["k1", "k2"], ["k2"])


def test_rt_109_memory_leak_detection():
    samples_ok = [100, 110, 115, 120]
    assert pv.validate_memory_leak_detection(samples_ok, allowed_growth_bytes=50)
    samples_bad = [100, 200, 400]
    assert not pv.validate_memory_leak_detection(samples_bad, allowed_growth_bytes=150)


def test_rt_110_sla_monitoring_metrics():
    good = {"p50": 10.0, "p95": 25.0, "error_rate": 0.01}
    assert pv.validate_sla_monitoring_metrics(good)
    bad = {"p50": 10.0, "p95": 5.0, "error_rate": 1.5}
    assert not pv.validate_sla_monitoring_metrics(bad)
