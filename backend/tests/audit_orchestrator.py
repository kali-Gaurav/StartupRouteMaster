import asyncio
import logging
import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch

# Root path adjustment for backend imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock external dependencies BEFORE importing Orchestrator
import core.nexus.audit.governor
core.nexus.audit.governor.nexus_governor = MagicMock()
core.nexus.audit.governor.nexus_governor.get_stats = AsyncMock(return_value={"cpu": 10, "ram": 20})

import core.infrastructure.resource_monitor
core.infrastructure.resource_monitor.resource_monitor = MagicMock()
core.infrastructure.resource_monitor.resource_monitor.get_surge_level = MagicMock(return_value=MagicMock(name="NORMAL"))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import BaseRoutingEngine, RoutingRequest, RoutingResponse
from core.route_engine.constraints import RouteConstraints
from core.data_utils.structures import Route, RouteSegment

# Mock Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit.orchestrator")

class MockEngine(BaseRoutingEngine):
    def __init__(self, name: str, yield_routes: List[Route]):
        self._name = name
        self._yield = yield_routes

    @property
    def engine_id(self) -> str:
        return self._name

    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        await asyncio.sleep(0.01)
        cloned_routes = [Route.from_dict(r.to_dict()) for r in self._yield]
        for r in cloned_routes: r.metadata["engine"] = self._name
        return RoutingResponse(engine_name=self._name, routes=cloned_routes, latency_ms=10.0, yield_count=len(cloned_routes))

    async def _resolve_cluster_ids(self, conn, code):
        return [123] # Mock cluster ID

class CrashingEngine(BaseRoutingEngine):
    @property
    def engine_id(self) -> str:
        return "crashing_engine"
    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        raise RuntimeError("Synthetic Crash")

async def setup_mock_orchestrator(engines_dict: Dict[str, BaseRoutingEngine]):
    mock_engine_base = AsyncMock()
    mock_engine_base._get_current_graph = AsyncMock(return_value=MagicMock())
    
    orch = UnifiedRoutingOrchestrator(mock_engine_base)
    orch.engines = engines_dict
    for name, eng in engines_dict.items():
        if name == "ultra_turbo_direct": orch.ultra_turbo = eng
        if name == "raptor": orch.raptor = eng
        if name == "fastpath_bfs": orch.fast_router = eng
        if name == "turbo_router": orch.turbo_router = eng
    
    orch.hydration_pipeline = MagicMock()
    orch.hydration_pipeline.execute = AsyncMock()
    return orch

def create_sample_route(train_no: str, departure_hour: int = 10) -> Route:
    dep = datetime(2026, 4, 1, departure_hour, 0)
    arr = dep + timedelta(hours=1)
    seg = RouteSegment(trip_id=int(train_no), train_number=train_no, departure_stop_id=100, arrival_stop_id=200,
                       departure_code="SRC", arrival_code="DST", departure_time=dep, arrival_time=arr,
                       duration_minutes=60, distance_km=100.0, fare=500.0)
    return Route(segments=[seg])

@pytest.mark.asyncio
async def test_all_audits():
    # 1. Setup Mocks
    mock_conn = MagicMock()
    # Mocking 'async with get_raw_transit_conn() as conn'
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_context_manager.__aexit__ = AsyncMock()

    with patch("database.session.get_raw_transit_conn", return_value=mock_context_manager), \
         patch("utils.station_utils.resolve_stations", return_value=(MagicMock(code="SRC", id=1), MagicMock(code="DST", id=2))), \
         patch("core.route_engine.orchestrator.text", side_effect=lambda x: x): # Mock text() for SQL
        
        # Test 1: Deduplication
        r_a = create_sample_route("111")
        r_b = create_sample_route("111")
        orch = await setup_mock_orchestrator({"a": MockEngine("a", [r_a]), "b": MockEngine("b", [r_b])})
        req = RoutingRequest(source_code="SRC", destination_code="DST", src_cluster_ids=[1], dst_cluster_ids=[2],
                             departure_date=datetime(2026, 4, 1), constraints=RouteConstraints(), limit=10)
        
        # We need to mock turbo_router._get_station_code used in orchestrator
        orch.turbo_router._get_station_code = MagicMock(return_value="STATION")

        res = await orch.search_all_tiers(req)
        assert len(res) == 1
        logger.info("✅ Audit 01 Passed.")

        # Test 6: Empty
        orch = await setup_mock_orchestrator({"empty": MockEngine("empty", [])})
        orch.turbo_router._get_station_code = MagicMock(return_value="STATION")
        res = await orch.search_all_tiers(req)
        assert len(res) == 0
        logger.info("✅ Audit 06 Passed.")

        # Test 21: Crash
        valid = create_sample_route("222")
        orch = await setup_mock_orchestrator({"fail": CrashingEngine(), "win": MockEngine("win", [valid])})
        orch.turbo_router._get_station_code = MagicMock(return_value="STATION")
        res = await orch.search_all_tiers(req)
        assert len(res) == 1
        logger.info("✅ Audit 21 Passed.")

if __name__ == "__main__":
    asyncio.run(test_all_audits())
    print("\n🎉 ALL TESTS PASSED.")
