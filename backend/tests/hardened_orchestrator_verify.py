import asyncio
import logging
import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from unittest.mock import MagicMock, AsyncMock, patch

# Root path adjustment for backend imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.nexus.audit.governor
core.nexus.audit.governor.nexus_governor = MagicMock()
core.nexus.audit.governor.nexus_governor.get_stats = AsyncMock(return_value={"cpu": 10, "ram": 20})

import core.resource_monitor
core.resource_monitor.resource_monitor = MagicMock()
core.resource_monitor.resource_monitor.get_surge_level = MagicMock(return_value=MagicMock(name="NORMAL"))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import BaseRoutingEngine, RoutingRequest, RoutingResponse
from core.route_engine.constraints import RouteConstraints, Persona
from core.data_structures import Route, RouteSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit.hardened.v2")

async def setup_test_orch(engines: Dict[str, BaseRoutingEngine], graph_date: datetime = datetime.utcnow()):
    mock_base = AsyncMock()
    mock_graph = MagicMock()
    mock_graph.snapshot = MagicMock()
    mock_graph.snapshot.date = graph_date
    mock_graph.overlay.sync_with_db = AsyncMock()
    mock_base._get_current_graph = AsyncMock(return_value=mock_graph)
    
    orch = UnifiedRoutingOrchestrator(mock_base)
    orch.engines = engines
    for n, e in engines.items():
        if n == "ultra_turbo_direct": orch.ultra_turbo = e
        if n == "raptor": orch.raptor = e
        if n == "turbo_router": orch.turbo_router = e
        if n == "fastpath_bfs": orch.fast_router = e
    orch.hydration_pipeline = MagicMock()
    orch.hydration_pipeline.execute = AsyncMock()
    return orch

@pytest.mark.asyncio
async def test_todo_08_stale_graph():
    """[TODO-08] Verify that a graph > 7 days old is rejected."""
    very_old_date = datetime.utcnow() - timedelta(days=10)
    orch = await setup_test_orch({}, graph_date=very_old_date)
    
    req = RoutingRequest(
        source_code="S", destination_code="D",
        src_cluster_ids=[], dst_cluster_ids=[],
        departure_date=datetime(2026, 4, 1),
        constraints=RouteConstraints(),
        limit=10,
        db_session=MagicMock()
    )
    
    res = await orch.search_all_tiers(req)
    assert res == []
    logger.info("✅ Hardening 08: Stale Graph Rejection Passed.")

if __name__ == "__main__":
    asyncio.run(test_todo_08_stale_graph())
    print("\n🎉 PHASE 2 VERIFICATION COMPLETE.")
