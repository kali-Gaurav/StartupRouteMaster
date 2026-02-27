import asyncio
import random
import psutil
import pytest

from core.validator.performance_validators import PerformanceValidator

pv = PerformanceValidator()


@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_queries_scaling_simulation():
    """Simulate many concurrent 'queries' using sleeps and validate P95."""
    async def worker(i):
        # simulate work with variable latency
        t = random.uniform(0.001, 0.02)
        await asyncio.sleep(t)
        return t * 1000.0  # ms

    tasks = [asyncio.create_task(worker(i)) for i in range(300)]
    results = await asyncio.gather(*tasks)

    # Validate P95 under a permissive threshold (50ms)
    assert pv.validate_concurrent_queries_scaling(results, p95_threshold_ms=50.0)


@pytest.mark.performance
def test_memory_leak_detection_simulation():
    """Simulate memory sampling and ensure growth within allowed budget."""
    proc = psutil.Process()
    samples = []
    # create some allocations but controlled
    temp = []
    for i in range(5):
        temp.append([0] * (10_000 * (i + 1)))
        samples.append(proc.memory_info().rss)

    # allow some growth but within budget
    assert pv.validate_memory_leak_detection(samples, allowed_growth_bytes=200 * 1024 * 1024)
