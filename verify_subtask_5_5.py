import asyncio
import logging
from unittest.mock import MagicMock, patch, AsyncMock
import os
import sys
from datetime import datetime

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.core.route_engine.engine import RailwayRouteEngine
from backend.core.route_engine.graph import TimeDependentGraph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-5.5")

async def test_predictive_hydration_logic():
    # 1. Setup Engine and Mock Graph
    engine = RailwayRouteEngine()
    mock_graph = MagicMock(spec=TimeDependentGraph)
    mock_graph.snapshot = MagicMock()
    mock_graph.snapshot.date = datetime.now()
    
    # Create some mock stops in stop_cache
    mock_stop = MagicMock()
    mock_stop.code = "NDLS"
    mock_graph.stop_cache = {101: mock_stop}
    
    # 2. Mock get_departures_from_stop to see if it's called
    mock_graph.get_departures_from_stop = MagicMock()
    
    logger.info("Testing _predictive_hydration background task...")
    
    # 3. Call hydration
    # We patch MAJOR_HUBS to ensure we only hit our mock stop
    with patch('backend.core.route_engine.hubs.MAJOR_HUBS', ["NDLS"]):
        await engine._predictive_hydration(mock_graph)
        
        # 4. Verify interaction
        # Should have called get_departures_from_stop for stop_id 101
        mock_graph.get_departures_from_stop.assert_called_once()
        args, kwargs = mock_graph.get_departures_from_stop.call_args
        assert args[0] == 101
        logger.info("✅ Verified: Hub ID 101 (NDLS) was hydrated.")

    logger.info("✅ Subtask 5.5: Predictive JIT Hydration logic Verified.")

if __name__ == "__main__":
    asyncio.run(test_predictive_hydration_logic())
