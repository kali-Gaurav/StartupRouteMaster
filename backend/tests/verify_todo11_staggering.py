import asyncio
import logging
import time
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Mocks to avoid real DB/Graph loading
import core.nexus.audit.governor
core.nexus.audit.governor.nexus_governor = MagicMock()
core.nexus.audit.governor.nexus_governor.get_stats = AsyncMock(return_value={"cpu": 10, "ram": 20})

import core.infrastructure.resource_monitor
core.infrastructure.resource_monitor.resource_monitor = MagicMock()
core.infrastructure.resource_monitor.resource_monitor.get_surge_level = MagicMock(return_value=MagicMock(name="NORMAL"))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import BaseRoutingEngine, RoutingRequest, RoutingResponse
from core.route_engine.constraints import RouteConstraints
from core.data_utils.structures import Route

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify.todo11")

class TimedEngine(BaseRoutingEngine):
    def __init__(self, name: str):
        self._name = name
        self.launch_time = None

    @property
    def engine_id(self) -> str: return self._name

    async def find_routes(self, request: RoutingRequest) -> RoutingResponse:
        self.launch_time = time.perf_counter()
        return RoutingResponse(engine_name=self._name, routes=[], latency_ms=1.0)
    
    async def _resolve_cluster_ids(self, conn, code): return []
    def _get_station_code(self, db, sid): return "X"

async def test_staggering_timing():
    # Setup Orchestrator with Timed Engines
    hub = TimedEngine("hub_tier_0")
    raptor = TimedEngine("raptor")
    
    mock_base = AsyncMock()
    # Mock graph to avoid init
    mock_graph = MagicMock()
    mock_graph.overlay.sync_with_db = AsyncMock()
    mock_base._get_current_graph = AsyncMock(return_value=mock_graph)
    
    orch = UnifiedRoutingOrchestrator(mock_base)
    orch.engines = {"hub_tier_0": hub, "raptor": raptor}
    orch.hub_router = hub
    orch.raptor = raptor
    # Need others for setup
    orch.ultra_turbo = TimedEngine("ut")
    orch.turbo_router = TimedEngine("turbo")
    orch.fast_router = TimedEngine("fast")
    orch.tbr_router = TimedEngine("tbr")
    orch.hydration_pipeline = MagicMock()
    orch.hydration_pipeline.execute = AsyncMock()

    req = RoutingRequest(
        source_code="NDLS", destination_code="BOM",
        departure_date=datetime.now(),
        constraints=RouteConstraints(),
        limit=10,
        src_cluster_ids=[], dst_cluster_ids=[],
        db_session=MagicMock()
    )

    # We need to bypass resolve_stations cluster resolve
    with patch("utils.station_utils.resolve_stations", return_value=(MagicMock(code="NDLS"), MagicMock(code="BOM"))), \
         patch("database.session.get_raw_transit_conn", return_value=AsyncMock()):
        
        # Start search
        await orch.search_all_tiers(req)
        
        # Check launch times
        t_hub = hub.launch_time
        t_raptor = raptor.launch_time
        
        if t_hub is None or t_raptor is None:
            logger.error("❌ Engines did not launch!")
            return False
            
        diff = (t_raptor - t_hub) * 1000
        logger.info(f"⏱ Staggering: RAPTOR launched {diff:.2f}ms after HUB.")
        
        # Wait a bit more for the loop to finish
        if diff >= 30: 
            logger.info("✅ TODO-11: Staggering verified.")
            return True
        else:
            logger.error(f"❌ TODO-11: Staggering too low ({diff:.2f}ms < 30ms)")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_staggering_timing())
    if not success: sys.exit(1)
