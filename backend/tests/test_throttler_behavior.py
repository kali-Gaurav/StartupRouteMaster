import asyncio
import pytest
import time
from datetime import datetime
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import RoutingRequest, RoutingResponse
from core.data_structures import Route, Persona
from core.route_engine.constraints import RouteConstraints

class MockEngine:
    def __init__(self, name, delay=0.1):
        self.name = name
        self.delay = delay
        self.call_count = 0
        self.last_limit = 0

    async def find_routes(self, request):
        self.call_count += 1
        self.last_limit = request.limit
        await asyncio.sleep(self.delay)
        return RoutingResponse(
            engine_name=self.name,
            routes=[],
            latency_ms=self.delay * 1000,
            yield_count=0
        )

@pytest.mark.asyncio
async def test_adaptive_throttling_logic():
    # Setup Orchestrator with mock engines
    orch = UnifiedRoutingOrchestrator(None)
    mock_raptor = MockEngine("raptor", delay=0.2) # Target is 850ms, so 200ms is healthy
    orch.engines["raptor"] = mock_raptor
    
    constraints = RouteConstraints(departure_date=datetime.now().date())
    request = RoutingRequest(
        source_code="GKP",
        destination_code="TVC",
        src_cluster_ids=[1],
        dst_cluster_ids=[2],
        departure_date=datetime.now(),
        constraints=constraints,
        limit=20
    )

    # 1. First run - Healthy
    results = await orch.search_all_tiers(request)
    throttler = orch.throttlers["raptor"]
    print(f"Cycle 1 Stats: {throttler.get_stats()}")
    assert throttler.limit_scale == 1.0
    assert mock_raptor.last_limit == 20

    # 2. Simulate Latency Spike (EWMA update)
    # Target is 850. Let's feed it 2000ms.
    throttler.record_latency(2000.0)
    print(f"Cycle 2 Stats (Stimulated): {throttler.get_stats()}")
    assert throttler.limit_scale < 1.0
    
    # 3. Second run - Should be Throttled
    results = await orch.search_all_tiers(request)
    print(f"Cycle 2 Effective Limit: {mock_raptor.last_limit}")
    assert mock_raptor.last_limit < 20
    assert mock_raptor.last_limit == throttler.get_effective_limit(20)

    # 4. Critical Latency Skip
    throttler.record_latency(5000.0) # > 3x target (850*3 = 2550)
    print(f"Cycle 3 Stats (Critical): {throttler.get_stats()}")
    assert throttler.should_skip() is True
    
    # Non-premium search should now skip RAPTOR
    mock_raptor.call_count = 0
    await orch.search_all_tiers(request)
    assert mock_raptor.call_count == 0


def test_nexus_governor_throttle_factor_formula():
    from core.nexus.audit.governor import NexusResourceGovernor
    g = NexusResourceGovernor(cpu_limit=80.0, ram_limit=80.0)

    # Example metrics
    cpu_percent = 68.0
    ram_percent = 75.0
    io_wait = 5.0
    redis_percent = 10.0

    expected_factor = round(max(
        min(1.0, cpu_percent / g.cpu_limit),
        min(1.0, ram_percent / g.ram_limit),
        min(1.0, io_wait / 100.0),
        min(1.0, redis_percent / 100.0)
    ), 2)

    assert expected_factor == 0.94


if __name__ == "__main__":
    asyncio.run(test_adaptive_throttling_logic())
